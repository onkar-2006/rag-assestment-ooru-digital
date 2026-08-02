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
                # 30.0 second max timeout rule for local LLM before falling back to hosted cloud API
                self.local_llm = ChatOpenAI(
                    openai_api_key="EMPTY",
                    openai_api_base=config.local_llm_url,
                    model_name=config.local_llm_model,
                    temperature=0.1,
                    request_timeout=30.0
                )
            except Exception as e:
                print(f"⚠️ [INIT WARNING] Local LLM setup failed: {e}")
                self.local_llm = None

        # ChatOpenAI client via OpenRouter API (Passes native usage tokens to LangSmith)
        self.openrouter_llm = ChatOpenAI(
            openai_api_key=config.openrouter_api_key,
            openai_api_base=config.openrouter_base_url,
            model_name=config.llm_model,
            temperature=0.1
        )

    def _is_local_llm_online(self) -> bool:
        """Fast ping health check (500ms timeout) to verify local Ollama engine presence."""
        if not config.use_local_llm or not self.local_llm:
            return False
        try:
            import requests
            base_host = config.local_llm_url.rstrip("/").rstrip("/v1")
            res = requests.get(f"{base_host}/api/tags", timeout=0.5)
            return res.status_code == 200
        except Exception:
            return False

    @traceable(name="llm_call")
    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM with Hosted API as PRIMARY (Groq / OpenRouter) for instant zero-latency responses.
        If Hosted API is over/unavailable, automatically failover to Local LLM.
        """
        # 1. Primary: Try Hosted ChatGroq API
        if self.groq_llm:
            try:
                res = self.groq_llm.invoke(prompt)
                answer = str(res.content).strip()
                if answer:
                    print(f"☁️ [LLM PROVIDER]: HOSTED GROQ API ({config.groq_model}) answered query!")
                    return answer
            except Exception as err:
                print(f"⚠️ [HOSTED API WARNING]: Groq API call failed or rate-limited ({err}). Trying OpenRouter...")

        # 2. Secondary: Try Hosted OpenRouter API
        if config.openrouter_api_key:
            try:
                res = self.openrouter_llm.invoke(prompt)
                answer = str(res.content).strip()
                if answer:
                    print(f"☁️ [LLM PROVIDER]: HOSTED OPENROUTER API ({config.llm_model}) answered query!")
                    return answer
            except Exception as err:
                print(f"⚠️ [HOSTED API WARNING]: OpenRouter API call failed ({err}). Falling back to Local LLM engine...")

        # 3. Fallback: Self-Hosted Local Ollama / vLLM LLM Engine
        if self._is_local_llm_online():
            try:
                res = self.local_llm.invoke(prompt)
                answer = str(res.content).strip()
                if answer:
                    print(f"🤖 [LLM PROVIDER FALLBACK]: LOCAL LLM (Ollama - {config.local_llm_model}) answered query!")
                    return answer
            except Exception as err:
                print(f"❌ [LLM PROVIDER ERROR]: Local LLM failed ({err}).")

        raise RuntimeError("All LLM providers (Hosted APIs and Local LLM) are currently unavailable.")

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
