from typing import List, Optional
from pydantic import BaseModel, Field

class InputGuardrailResult(BaseModel):
    """Result of Input Safety Inspection."""
    is_safe: bool = Field(..., description="Whether input query is safe for processing")
    threat_type: Optional[str] = Field(None, description="Identified threat category (e.g., 'prompt_injection', 'toxic_content', 'none')")
    reasoning: str = Field(..., description="Explanation of safety evaluation")

class OutputGuardrailResult(BaseModel):
    """Result of Output Faithfulness Inspection."""
    is_faithful: bool = Field(..., description="Whether generated response is strictly grounded in context")
    hallucination_detected: bool = Field(False, description="Whether hallucinated ungrounded claims were detected")
    reasoning: str = Field(..., description="Explanation of faithfulness check")
