import re
from typing import Dict, Any
from backend.guardrails.schemas import InputGuardrailResult

class InputGuardrail:
    """
    Input Safety Guardrail scanning for Prompt Injection, System Override attempts,
    Jailbreak patterns, and toxic content.
    """
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+all\s+(previous|system)\s+prompts",
        r"system\s+prompt\s+override",
        r"you\s+are\s+now\s+in\s+dan\s+mode",
        r"do\s+anything\s+now",
        r"act\s+as\s+an\s+unfiltered\s+ai",
        r"forget\s+your\s+rules",
        r"override\s+security\s+protocols",
        r"show\s+me\s+your\s+system\s+instructions",
        r"reveal\s+(api|secret)\s+keys?"
    ]

    def __init__(self):
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def validate_input(self, user_query: str) -> InputGuardrailResult:
        """Validates user query against prompt injection and malicious attempts."""
        clean_query = user_query.strip()
        
        # 1. Pattern Regex Matching
        for pattern in self.compiled_patterns:
            if pattern.search(clean_query):
                return InputGuardrailResult(
                    is_safe=False,
                    threat_type="prompt_injection",
                    reasoning=f"Query matched prompt injection security pattern: '{pattern.pattern}'"
                )

        # 2. Length & Suspicious Special Character Check
        if len(clean_query) > 2000 and clean_query.count("{") > 10:
            return InputGuardrailResult(
                is_safe=False,
                threat_type="malicious_payload",
                reasoning="Query payload size or formatting exceeds safety thresholds."
            )

        return InputGuardrailResult(
            is_safe=True,
            threat_type="none",
            reasoning="Input query passed all safety checks."
        )
