import json
import requests
from typing import List, Dict, Any, Optional
from langsmith import traceable
from langchain_groq import ChatGroq
from backend.agent.hybrid_retriever import HybridRetriever
from backend.agent.models import Citation, StructuredExtractionSchema
from backend.agent.prompt import (
    GROUNDED_QA_PROMPT, 
    STRUCTURED_EXTRACTION_PROMPT, 
    SELF_REPAIR_PROMPT,
    SECTION_SUMMARIZATION_PROMPT
)
from backend.config import config

from langchain_openai import ChatOpenAI

class AgentTools:
    """
    Agentic Tool Suite supporting ChatGroq / ChatOpenAI LLM inference:
    1. Hybrid Context Retrieval (Dense + BM25 + RRF)
    2. Structured JSON Data Extraction with Self-Correction
    3. Section-Aware Map-Reduce Summarization
    """
    def __init__(self, hybrid_retriever: Optional[HybridRetriever] = None):
        self.retriever = hybrid_retriever or HybridRetriever()
        self.groq_llm = None
        if config.groq_api_key:
            try:
                self.groq_llm = ChatGroq(
                    groq_api_key=config.groq_api_key,
                    model_name=config.groq_model,
                    temperature=0.1
                )
            except Exception:
                self.groq_llm = None

        # Self-Hosted / Fine-Tuned Local LLM Client (vLLM / Ollama / LM Studio)
        self.local_llm = None
        if config.use_local_llm:
            try:
                self.local_llm = ChatOpenAI(
                    openai_api_key="EMPTY",
                    openai_api_base=config.local_llm_url,
                    model_name=config.local_llm_model,
                    temperature=0.1
                )
            except Exception:
                self.local_llm = None

        # ChatOpenAI client via OpenRouter API (Passes native usage tokens to LangSmith)
        self.openrouter_llm = ChatOpenAI(
            openai_api_key=config.openrouter_api_key,
            openai_api_base=config.openrouter_base_url,
            model_name=config.llm_model,
            temperature=0.1
        )

    @traceable(name="llm_call")
    def _call_llm(self, prompt: str) -> str:
        """Call LLM via Self-Hosted vLLM, ChatGroq, or ChatOpenAI with automatic LangSmith tracing."""
        # 1. Priority: Fine-Tuned Local vLLM Server (If enabled & running)
        if config.use_local_llm and self.local_llm:
            try:
                res = self.local_llm.invoke(prompt)
                return str(res.content).strip()
            except Exception:
                pass  # Fallback to Cloud APIs if local server is unreachable

        # 2. Priority: ChatGroq API
        if self.groq_llm:
            try:
                res = self.groq_llm.invoke(prompt)
                return str(res.content).strip()
            except Exception:
                pass

        # 3. Priority: OpenRouter API Fallback
        res = self.openrouter_llm.invoke(prompt)
        return str(res.content).strip()



    @traceable(name="tool_retrieve_context")
    def retrieve_context(self, query: str, limit: int = 5, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Tool 1: Hybrid Retrieval Engine.
        Executes Dense Vector + BM25 Lexical + Reciprocal Rank Fusion search.
        """
        return self.retriever.search(query, top_k=limit, rrf_k=config.rrf_k, session_id=session_id)


    @traceable(name="tool_extract_structured_json")
    def extract_structured_json(self, user_request: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:

        """
        Tool 2: Structured JSON Extraction with Reflection Repair Loop.
        """
        context_str = "\n\n".join([f"--- Chunk ID: {c['chunk_id']} (Section: {c['section_path']}, Pages: {c['page_numbers']}) ---\n{c['content']}" for c in chunks])
        prompt = STRUCTURED_EXTRACTION_PROMPT.format(context_str=context_str, user_request=user_request)

        raw_output = self._call_llm(prompt)
        
        # Self-repair reflection loop if JSON is malformed
        for attempt in range(2):
            try:
                # Clean markdown backticks if present
                clean_json_str = raw_output.replace("```json", "").replace("```", "").strip()
                parsed_json = json.loads(clean_json_str)
                # Validate against Pydantic schema
                validated = StructuredExtractionSchema(**parsed_json)
                return validated.model_dump()
            except Exception as err:
                repair_prompt = SELF_REPAIR_PROMPT.format(malformed_output=raw_output, error_message=str(err))
                raw_output = self._call_llm(repair_prompt)
        
        return {"status": "error", "message": "Failed to parse structured JSON after repair loop", "raw_output": raw_output}

    def summarize_document_section(self, section_query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Tool 3: Section Summarizer Engine.
        """
        context_str = "\n\n".join([f"[Section: {c['section_path']} | Pages: {c['page_numbers']}]\n{c['content']}" for c in chunks])
        prompt = SECTION_SUMMARIZATION_PROMPT.format(context_str=context_str)
        return self._call_llm(prompt)
