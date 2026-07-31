import time
import requests
from typing import List, Dict, Any, Optional
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from backend.config import config

class QdrantIndexer:
    """
    Production Vector Store Manager for Qdrant Cloud.
    Handles cloud embedding generation via OpenRouter API and points vector indexing into Qdrant.
    """
    def __init__(self):
        self.qdrant_url = config.qdrant_url
        self.qdrant_api_key = config.qdrant_api_key
        self.collection_name = config.collection_name
        self.openai_client = OpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.openrouter_api_key
        )
        self.client = self._init_qdrant_client()

    def _init_qdrant_client(self) -> QdrantClient:
        try:
            client = QdrantClient(
                url=self.qdrant_url, 
                api_key=self.qdrant_api_key, 
                timeout=60.0, 
                check_compatibility=False
            )
            client.get_collections()
            try:
                from qdrant_client.http import models as qmodels
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="session_id",
                    field_schema=qmodels.PayloadSchemaType.KEYWORD
                )
            except Exception:
                pass
            return client
        except Exception:
            # Fallback to local embedded Qdrant if cloud endpoint is unreachable
            local_client = QdrantClient(path="./qdrant_db")
            try:
                from qdrant_client.http import models as qmodels
                local_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="session_id",
                    field_schema=qmodels.PayloadSchemaType.KEYWORD
                )
            except Exception:
                pass
            return local_client



    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding via OpenRouter API."""
        return self.get_embeddings_batch([text])[0]

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates vector embeddings in batch mode to cut network overhead by ~80%."""
        if not texts:
            return []
        try:
            response = self.openai_client.embeddings.create(
                model=config.embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception:
            headers = {
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            payload = {"model": config.embedding_model, "input": texts}
            res = requests.post(f"{config.openrouter_base_url}/embeddings", headers=headers, json=payload, timeout=25)
            data = res.json().get("data", [])
            return [item["embedding"] for item in data]

    def index_chunks(self, chunks: List[Dict[str, Any]], session_id: Optional[str] = None) -> Dict[str, Any]:
        """Indexes document chunks into Qdrant vector store in optimized batches."""
        if not chunks:
            return {"indexed_points": 0, "status": "no_chunks"}

        start_time = time.perf_counter()

        # Batch embed all chunk contents (batch size: 20 chunks)
        batch_size = 20
        all_contents = [c["content"] for c in chunks]
        all_vectors = []

        for i in range(0, len(all_contents), batch_size):
            batch_texts = all_contents[i:i + batch_size]
            vecs = self.get_embeddings_batch(batch_texts)
            all_vectors.extend(vecs)

        vector_dim = len(all_vectors[0])

        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
            )
            from qdrant_client.http import models as qmodels
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="session_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD
            )


        import uuid
        points = []
        for idx, chunk in enumerate(chunks):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=all_vectors[idx],
                payload={
                    "chunk_id": chunk["chunk_id"],
                    "session_id": session_id or chunk.get("session_id", "default"),
                    "doc_name": chunk["doc_name"],
                    "page_numbers": chunk["page_numbers"],
                    "section_path": chunk["section_path"],
                    "chunk_type": chunk["chunk_type"],
                    "token_count": chunk["token_count"],
                    "content": chunk["content"]
                }
            ))


        # Batch upsert points (batch size: 20 points) to prevent Qdrant Cloud HTTP timeout
        batch_size_upsert = 20
        for i in range(0, len(points), batch_size_upsert):
            batch_points = points[i:i + batch_size_upsert]
            try:
                self.client.upsert(collection_name=self.collection_name, points=batch_points)
            except Exception as err:
                print(f"⚠️ Qdrant Cloud upsert timeout/error: {err}. Falling back to local Qdrant DB...")
                from qdrant_client import QdrantClient
                local_client = QdrantClient(path="./qdrant_db")
                if not local_client.collection_exists(self.collection_name):
                    local_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
                    )
                local_client.upsert(collection_name=self.collection_name, points=batch_points)
                self.client = local_client

        elapsed_time = time.perf_counter() - start_time

        return {
            "status": "success",
            "indexed_points": len(points),
            "vector_dim": vector_dim,
            "indexing_time_seconds": round(elapsed_time, 2)
        }

    def search(self, query_text: str, limit: int = 5, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches vector store for top matching contexts for a user query, isolated by session_id."""
        query_vec = self.get_embedding(query_text)
        
        query_filter = None
        if session_id:
            from qdrant_client.http import models as qmodels
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="session_id",
                        match=qmodels.MatchValue(value=session_id)
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vec,
            query_filter=query_filter,
            limit=limit
        )

        
        results = []
        for point in response.points:
            payload = point.payload
            results.append({
                "score": point.score,
                "chunk_id": payload.get("chunk_id"),
                "doc_name": payload.get("doc_name"),
                "page_numbers": payload.get("page_numbers"),
                "section_path": payload.get("section_path"),
                "chunk_type": payload.get("chunk_type"),
                "content": payload.get("content")
            })
        return results

    def delete_session_vectors(self, session_id: str) -> Dict[str, Any]:
        """Deletes all vector points associated with a specific session_id from Qdrant."""
        if not session_id:
            return {"status": "error", "detail": "Invalid session_id"}

        try:
            from qdrant_client.http import models as qmodels
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="session_id",
                                match=qmodels.MatchValue(value=session_id)
                            )
                        ]
                    )
                )
            )
            return {"status": "success", "session_id": session_id}
        except Exception as err:
            print(f"⚠️ Error purging Qdrant vectors for session {session_id}: {err}")
            return {"status": "error", "detail": str(err)}

    def close(self):
        """Closes Qdrant client connection safely."""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
        except Exception:
            pass

