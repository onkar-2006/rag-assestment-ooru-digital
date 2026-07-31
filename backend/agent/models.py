from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Citation(BaseModel):
    """Citation metadata identifying source document location and similarity score."""
    doc_name: str = Field(description="Name of source document")
    page_numbers: List[int] = Field(default_factory=list, description="Page numbers referenced")
    section_path: str = Field(description="Breadcrumb header section path")
    chunk_id: str = Field(description="Unique ID of chunk")
    score: float = Field(0.0, description="Dense Cosine similarity or RRF relevance score")

class ExtractedField(BaseModel):
    """Key-value extracted data field with confidence/reference."""
    field_name: str = Field(description="Name of the extracted entity or field")
    value: Any = Field(description="Extracted field value")
    context_snippet: Optional[str] = Field(None, description="Relevant source snippet supporting extraction")

class StructuredExtractionSchema(BaseModel):
    """Pydantic model for structured document data extraction."""
    document_title: Optional[str] = Field(None, description="Title of document")
    extracted_fields: List[ExtractedField] = Field(default_factory=list, description="Extracted key-value pairs")
    citations: List[Citation] = Field(default_factory=list, description="Supporting document citations")

class AgentResponse(BaseModel):
    """Unified final response model."""
    answer: str = Field(description="Grounded response answer")
    intent: str = Field(description="Determined user query intent ('greeting', 'document_qa', 'structured_extraction', 'summarization')")
    citations: List[Citation] = Field(default_factory=list, description="Document citations with similarity scores")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted JSON data if requested")

