import math
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from backend.store.qdrant_indexer import QdrantIndexer
from backend.config import config

class HybridRetriever:
    """
    Production Hybrid Retriever combining Dense Vector Search (Qdrant Cosine)
    and Sparse Lexical Search (BM25), fused via Reciprocal Rank Fusion (RRF).
    """
    def __init__(self, indexer: Optional[QdrantIndexer] = None):
        self.indexer = indexer or QdrantIndexer()
        self.bm25: Optional[BM25Okapi] = None
        self.indexed_chunks: List[Dict[str, Any]] = []

    def build_bm25_index(self, chunks: List[Dict[str, Any]]):
        """Indexes document chunks into the BM25 lexical engine."""
        self.indexed_chunks = chunks
        corpus = [chunk["content"].lower().split() for chunk in chunks]
        if corpus:
            self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 5, rrf_k: int = 60, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Executes Hybrid Retrieval (Dense Vector + BM25 Lexical + Reciprocal Rank Fusion),
        isolated by session_id.
        """
        # 1. Dense Vector Search Stream via Qdrant Cloud (filtered strictly by session_id)
        dense_results = self.indexer.search(query, limit=top_k * 2, session_id=session_id)

        # 2. Sparse BM25 Search Stream
        bm25_results = []
        if self.bm25 and self.indexed_chunks:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            
            # Sort top BM25 scores
            top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k * 2]
            for idx in top_indices:
                if bm25_scores[idx] > 0:
                    chunk = self.indexed_chunks[idx]
                    bm25_results.append({
                        "score": float(bm25_scores[idx]),
                        "chunk_id": chunk["chunk_id"],
                        "doc_name": chunk["doc_name"],
                        "page_numbers": chunk["page_numbers"],
                        "section_path": chunk["section_path"],
                        "chunk_type": chunk["chunk_type"],
                        "content": chunk["content"]
                    })

        # 3. Reciprocal Rank Fusion (RRF) Reranking
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}

        # Process Dense Ranks
        for rank, res in enumerate(dense_results, 1):
            cid = res["chunk_id"]
            chunk_map[cid] = res
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))

        # Process BM25 Ranks
        for rank, res in enumerate(bm25_results, 1):
            cid = res["chunk_id"]
            if cid not in chunk_map:
                chunk_map[cid] = res
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))

        # Sort combined results by RRF score
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]

        # Theoretical max RRF score for rank 1 in both streams: 1/61 + 1/61 = 0.032786
        max_possible_rrf = (1.0 / (rrf_k + 1)) * 2.0

        hybrid_results = []
        for cid in sorted_chunk_ids:
            item = chunk_map[cid].copy()
            raw_rrf = rrf_scores[cid]
            # If Qdrant dense vector score exists (0-1.0 cosine similarity), use it; otherwise normalize RRF
            raw_cosine = item.get("score", 0.0)
            if raw_cosine > 0.0:
                normalized_score = min(1.0, max(0.0, raw_cosine))
            else:
                normalized_score = min(1.0, raw_rrf / max_possible_rrf)
            
            item["rrf_score"] = round(normalized_score, 4)
            hybrid_results.append(item)

        return hybrid_results
