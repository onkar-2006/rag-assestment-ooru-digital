import os
import time
import uuid
import shutil
import json
from typing import Dict, Any, Optional, List


from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from backend.pipeline import DocumentIntelligencePipeline
from backend.endpoint.schemas import UploadResponse, ChatRequest, ChatResponse, CitationDTO
from backend.endpoint.memory_store import session_store

app = FastAPI(
    title="Agentic Document Intelligence Assistant API",
    description="Production REST Endpoints supporting Document Upload, Hybrid RAG, LangGraph Agent Workflow, and Citation Similarity Scores.",
    version="1.0.0"
)

# Enable CORS for web frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = DocumentIntelligencePipeline()
TEMP_UPLOAD_DIR = "./temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Agentic Document Intelligence Assistant API",
        "version": "1.0.0"
    }

from sse_starlette.sse import EventSourceResponse

@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_document(session_id: Optional[str] = None, file: UploadFile = File(...)):
    """
    POST /api/documents/upload
    Uploads document (.pdf, .docx), parses structure, chunks section-aware breadcrumbs,
    indexes Qdrant Cloud vectors, updates in-memory BM25 index, and returns session_id.
    Supports uploading multiple documents into the same session_id.
    """
    start_time = time.perf_counter()
    active_session_id = session_id or f"session_{uuid.uuid4().hex[:10]}"
    file_path = os.path.join(TEMP_UPLOAD_DIR, f"{active_session_id}_{file.filename}")

    # Save uploaded file asynchronously
    try:
        allowed_exts = [".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_exts:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{file.filename}'. Supported formats: .pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp"
            )
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(err)}")

    # Process Document via Pipeline
    try:
        parsed_doc = pipeline.parser.parse(file_path)
        chunks = pipeline.chunker.chunk_document(parsed_doc)
        indexing_res = pipeline.indexer.index_chunks(chunks, session_id=active_session_id)


        # Create or Update Multi-Document Session Store
        session_store.create_or_update_session(
            session_id=active_session_id,
            doc_name=parsed_doc["doc_name"],
            chunks=chunks,
            pipeline=pipeline
        )

        elapsed = round(time.perf_counter() - start_time, 2)
        return UploadResponse(
            status="success",
            session_id=active_session_id,
            doc_name=parsed_doc["doc_name"],
            total_pages=parsed_doc["total_pages"],
            total_chunks=len(chunks),
            indexed_points=indexing_res.get("indexed_points", 0),
            processing_time_seconds=elapsed
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(err)}")

@app.post("/api/chat/message", response_model=ChatResponse)
async def chat_message(request: ChatRequest):
    """
    POST /api/chat/message
    Executes LangGraph Agent Workflow for user query, returning grounded answers
    along with citations containing exact similarity match scores (RRF / Cosine).
    """
    start_time = time.perf_counter()
    session = session_store.get_session(request.session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session ID '{request.session_id}' not found in memory store. Please upload a document first.")

    workflow = session["workflow"]
    history = session["history"]

    # Execute LangGraph Workflow with strict session_id isolation
    try:
        agent_response = workflow.run(request.message, history=history, session_id=request.session_id)

        
        # Save interaction to in-memory session history
        session_store.add_history(request.session_id, request.message, agent_response.answer)

        # Build Citations DTO with Similarity Match Scores
        citation_dtos = []
        for c in agent_response.citations:
            citation_dtos.append(CitationDTO(
                doc_name=c.doc_name,
                page_numbers=c.page_numbers,
                section_path=c.section_path,
                chunk_id=c.chunk_id,
                similarity_score=round(c.score, 4)
            ))

        elapsed = round(time.perf_counter() - start_time, 2)
        return ChatResponse(
            session_id=request.session_id,
            intent=agent_response.intent,
            answer=agent_response.answer,
            citations=citation_dtos,
            extracted_data=agent_response.extracted_data,
            elapsed_seconds=elapsed
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Agent workflow execution failed: {str(err)}")

@app.get("/api/chat/stream")
async def chat_stream(session_id: str, message: str):
    """
    GET /api/chat/stream
    Token-by-Token Server-Sent Events (SSE) Streaming endpoint.
    Streams answer tokens in real-time followed by full citations payload.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session ID '{session_id}' not found. Please upload a document first.")

    workflow = session["workflow"]
    history = session["history"]

    async def event_generator():
        # Execute workflow with strict session_id isolation
        agent_response = workflow.run(message, history=history, session_id=session_id)
        session_store.add_history(session_id, message, agent_response.answer)


        # Stream answer word by word with real Gemini-style typing pacing
        words = agent_response.answer.split(" ")
        for i, word in enumerate(words):
            token_data = {"token": word + (" " if i < len(words) - 1 else "")}
            yield {"event": "token", "data": json.dumps(token_data)}
            import asyncio
            await asyncio.sleep(0.035)  # 35ms Gemini-style smooth typing delay


        # Yield citations event
        citations_data = [
            {
                "doc_name": c.doc_name,
                "page_numbers": c.page_numbers,
                "section_path": c.section_path,
                "chunk_id": c.chunk_id,
                "similarity_score": round(c.score, 4)
            }
            for c in agent_response.citations
        ]
        yield {"event": "citations", "data": json.dumps(citations_data)}
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_generator())

@app.post("/api/session/terminate")
async def terminate_session(request: Dict[str, Any]):
    """
    POST /api/session/terminate
    Purges Qdrant vector database embeddings and clears in-memory session data.
    Supports standard JSON requests and navigator.sendBeacon unload payloads.
    """
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id in request body")

    deleted = session_store.delete_session(session_id)
    return {
        "status": "success" if deleted else "not_found",
        "session_id": session_id,
        "detail": f"Session '{session_id}' vectors purged from Qdrant and memory store."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.endpoint.router:app", host="0.0.0.0", port=8000, reload=True)

