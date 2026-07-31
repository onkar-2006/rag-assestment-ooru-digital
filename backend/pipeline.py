import time
import os
import sys
from typing import Dict, List, Any
from backend.parser.document_parser import UniversalDocumentParser
from backend.chunker.section_chunker import SectionAwareChunker
from backend.store.qdrant_indexer import QdrantIndexer
from backend.config import config

# Force UTF-8 output encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

class DocumentIntelligencePipeline:
    """
    Production Document Intelligence Pipeline.
    Supports PDF and DOCX ingestion -> Section-Aware Chunking -> Qdrant Cloud Vector Indexing.
    """
    def __init__(self):
        self.parser = UniversalDocumentParser()
        self.chunker = SectionAwareChunker(
            target_max_tokens=config.target_max_tokens,
            overlap_tokens=config.overlap_tokens
        )
        self.indexer = QdrantIndexer()

    def process_and_index_document(self, file_path: str) -> Dict[str, Any]:
        """
        Executes end-to-end processing pipeline for a PDF or DOCX document.
        """
        pipeline_start = time.perf_counter()

        print(f"==================================================")
        print(f" 🚀 Document Intelligence Pipeline: {os.path.basename(file_path)}")
        print(f"==================================================")

        # Stage 1: Universal Document Parsing (PDF & DOCX)
        print("📄 Stage 1: Parsing Document Structure...")
        parsed_doc = self.parser.parse(file_path)
        print(f"   ✓ Parsed {parsed_doc['total_pages']} pages in {parsed_doc['processing_time_seconds']}s ({parsed_doc['pages_per_second']} pages/sec)")

        # Stage 2: Section-Aware Semantic Chunking
        print("\n🧩 Stage 2: Generating Section-Aware Chunks...")
        chunks = self.chunker.chunk_document(parsed_doc)
        print(f"   ✓ Generated {len(chunks)} contextual chunks")

        # Stage 3: OpenRouter Embeddings & Qdrant Vector Indexing
        print("\n🌐 Stage 3: Indexing Vector Embeddings to Qdrant...")
        indexing_result = self.indexer.index_chunks(chunks)
        print(f"   ✓ Indexed {indexing_result['indexed_points']} points into Qdrant (Dimension: {indexing_result['vector_dim']})")

        total_elapsed = round(time.perf_counter() - pipeline_start, 2)
        print(f"\n==================================================")
        print(f" ✅ PIPELINE COMPLETED IN {total_elapsed} SECONDS!")
        print(f"==================================================\n")

        return {
            "status": "success",
            "doc_name": parsed_doc["doc_name"],
            "total_pages": parsed_doc["total_pages"],
            "total_chunks": len(chunks),
            "indexing_result": indexing_result,
            "total_elapsed_seconds": total_elapsed
        }

    def search_context(self, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Queries Qdrant for context relevant to user prompt."""
        return self.indexer.search(query, limit=limit)

