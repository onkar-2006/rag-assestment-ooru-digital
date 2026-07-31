from typing import List, Dict, Any, Optional
from backend.pipeline import DocumentIntelligencePipeline
from backend.agent.hybrid_retriever import HybridRetriever
from backend.agent.workflow import LangGraphDocumentWorkflow

class SessionMemoryStore:
    """
    In-Memory Session Store maintaining multi-turn state, document chunks,
    BM25 indexes, and LangGraph workflow instances per session.
    Supports multi-document session aggregation.
    """
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_or_update_session(self, session_id: str, doc_name: str, chunks: List[Dict[str, Any]], pipeline: DocumentIntelligencePipeline) -> Dict[str, Any]:
        """Creates or appends document chunks to an existing session."""
        if session_id in self._sessions:
            existing = self._sessions[session_id]
            existing["doc_names"].append(doc_name)
            existing["chunks"].extend(chunks)
            # Rebuild unified hybrid index across all uploaded documents
            existing["hybrid_retriever"].build_bm25_index(existing["chunks"])
            return existing

        # Create new session
        hybrid_retriever = HybridRetriever(pipeline.indexer)
        hybrid_retriever.build_bm25_index(chunks)
        workflow = LangGraphDocumentWorkflow(hybrid_retriever)

        session_data = {
            "session_id": session_id,
            "doc_names": [doc_name],
            "chunks": chunks,
            "hybrid_retriever": hybrid_retriever,
            "workflow": workflow,
            "history": []
        }
        self._sessions[session_id] = session_data
        return session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves session state from in-memory store."""
        return self._sessions.get(session_id)

    def add_history(self, session_id: str, user_msg: str, assistant_msg: str):
        """Appends user and assistant messages to in-memory session history."""
        session = self.get_session(session_id)
        if session:
            session["history"].append({"role": "user", "content": user_msg})
            session["history"].append({"role": "assistant", "content": assistant_msg})


# Global singleton in-memory session store
session_store = SessionMemoryStore()
