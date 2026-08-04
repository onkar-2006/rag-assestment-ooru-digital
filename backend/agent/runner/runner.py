import os
import sys
import time
from typing import List, Dict, Any, Optional
from backend.pipeline import DocumentIntelligencePipeline
from backend.agent.hybrid_retriever.hybrid_retriever import HybridRetriever
from backend.agent.workflow.workflow import LangGraphDocumentWorkflow

# Force UTF-8 output encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

class DocumentAgentRunner:
    """
    Master Production CLI Runner for Agentic Document Assistant with Hybrid RAG.
    """
    def __init__(self, doc_path: Optional[str] = None):
        self.pipeline = DocumentIntelligencePipeline()
        self.hybrid_retriever = HybridRetriever(self.pipeline.indexer)
        self.workflow = None

        if doc_path:
            self.load_document(doc_path)

    def load_document(self, file_path: str):
        """Ingests document, indexes Qdrant Cloud vectors, and builds BM25 lexical index."""
        print(f"📄 Processing document into Hybrid Index: {os.path.basename(file_path)}...")
        
        # 1. Parse Document & Index Vector Store
        parsed_doc = self.pipeline.parser.parse(file_path)
        chunks = self.pipeline.chunker.chunk_document(parsed_doc)
        self.pipeline.indexer.index_chunks(chunks)

        # 2. Build BM25 Index
        self.hybrid_retriever.build_bm25_index(chunks)
        
        # 3. Instantiate LangGraph Workflow
        self.workflow = LangGraphDocumentWorkflow(self.hybrid_retriever)
        print(f"✓ Document ready! Built Hybrid Index with {len(chunks)} chunks.\n")

    def ask(self, query: str) -> Dict[str, Any]:
        """Executes agent workflow for user prompt."""
        if not self.workflow:
            raise ValueError("No document loaded into agent runner!")

        start_time = time.perf_counter()
        response = self.workflow.run(query)
        elapsed = round(time.perf_counter() - start_time, 2)

        return {
            "query": query,
            "intent": response.intent,
            "answer": response.answer,
            "citations": [c.model_dump() for c in response.citations],
            "extracted_data": response.extracted_data,
            "elapsed_seconds": elapsed
        }
