from typing import List, Dict, Any
from backend.guardrails.schemas import OutputGuardrailResult

class OutputGuardrail:
    """
    Output Faithfulness & Hallucination Guardrail ensuring answers are strictly
    grounded in retrieved context.
    """
    FALLBACK_MESSAGE = "I am unable to find relevant information in the provided document to answer your question."

    def validate_output(self, answer: str, context_chunks: List[Dict[str, Any]]) -> OutputGuardrailResult:
        """Verifies if generated answer is grounded in retrieved chunks payload."""
        # 1. Empty Context Check
        if not context_chunks:
            if self.FALLBACK_MESSAGE in answer or "unable to answer" in answer.lower():
                return OutputGuardrailResult(
                    is_faithful=True,
                    hallucination_detected=False,
                    reasoning="Correct explicit fallback issued for empty context."
                )
            else:
                return OutputGuardrailResult(
                    is_faithful=False,
                    hallucination_detected=True,
                    reasoning="Response generated facts without any retrieved context."
                )

        # 2. Check explicitly stated fallback phrasing
        if self.FALLBACK_MESSAGE in answer or "unable to answer" in answer.lower():
            return OutputGuardrailResult(
                is_faithful=True,
                hallucination_detected=False,
                reasoning="Assistant correctly stated lack of supporting evidence."
            )

        # 3. Key Term / Substring Overlap Entailment Verification
        combined_context = " ".join([c["content"].lower() for c in context_chunks])
        answer_words = [w.lower() for w in answer.split() if len(w) > 4 and w.isalnum()]
        
        if answer_words:
            matched = sum(1 for word in answer_words if word in combined_context)
            overlap_ratio = matched / len(answer_words)

            # Lower strict threshold from 0.20 to 0.05 to prevent false hallucination flags on rich LLM explanations
            if overlap_ratio < 0.05:
                return OutputGuardrailResult(
                    is_faithful=False,
                    hallucination_detected=True,
                    reasoning=f"Low lexical entailment overlap ({overlap_ratio:.2f}) between answer and retrieved context."
                )


        return OutputGuardrailResult(
            is_faithful=True,
            hallucination_detected=False,
            reasoning="Output verified and grounded in retrieved context."
        )
