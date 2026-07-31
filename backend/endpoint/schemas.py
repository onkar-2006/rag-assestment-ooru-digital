from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class UploadResponse(BaseModel):
    """Document upload endpoint response."""
    status: str = "success"
    session_id: str
    doc_name: str
    total_pages: int
    total_chunks: int
    indexed_points: int
    processing_time_seconds: float

class CitationDTO(BaseModel):
    """Citation data transfer object with similarity score."""
    doc_name: str
    page_numbers: List[int]
    section_path: str
    chunk_id: str
    similarity_score: float = Field(..., description="Hybrid RRF or Cosine Similarity score match")

class ChatRequest(BaseModel):
    """Chat message request."""
    session_id: str = Field(..., description="Unique session identifier for multi-turn memory")
    message: str = Field(..., description="User query prompt")

class ChatResponse(BaseModel):
    """Chat message response with similarity scores."""
    session_id: str
    intent: str
    answer: str
    citations: List[CitationDTO] = Field(default_factory=list, description="Ranked context citations with similarity scores")
    extracted_data: Optional[Dict[str, Any]] = None
    elapsed_seconds: float
