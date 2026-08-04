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
    SECTION_SUMMARIZATION_PROMPT,
    CROSS_DOCUMENT_REASONING_PROMPT
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
            except Exception as e:
                print(f"⚠️ Failed to initialize ChatGroq: {e}")

        self.openrouter_llm = None
        if config.openrouter_api_key:
            try:
                self.openrouter_llm = ChatOpenAI(
                    model_name=config.llm_model,
                    openai_api_key=config.openrouter_api_key,
                    openai_api_base="https://openrouter.ai/api/v1",
                    temperature=0.1
                )
            except Exception as e:
                print(f"⚠️ Failed to initialize OpenRouter: {e}")


        # Local Ollama fallback LLM
        self.local_llm_url = f"{config.local_llm_url}/api/generate"
        self.local_model = config.local_llm_model


    def _call_llm(self, prompt: str) -> str:
        """
        Executes LLM call with priority order:
        1. Hosted ChatGroq API (llama-3.3-70b-versatile)
        2. Hosted OpenRouter API (openai/gpt-4o-mini)
        3. Local Self-Hosted Ollama (qwen2.5:0.5b)
        """
        # Primary #1: ChatGroq API
        if self.groq_llm:
            try:
                response = self.groq_llm.invoke(prompt)
                print("☁️ [LLM PROVIDER]: HOSTED GROQ API (llama-3.3-70b-versatile) answered query!")
                return response.content
            except Exception as err:
                print(f"⚠️ [LLM PROVIDER FALLBACK]: Groq API failed or rate-limited ({err}). Switching to OpenRouter...")

        # Secondary #2: OpenRouter API
        if self.openrouter_llm:
            try:
                response = self.openrouter_llm.invoke(prompt)
                print("☁️ [LLM PROVIDER]: HOSTED OPENROUTER API (openai/gpt-4o-mini) answered query!")
                return response.content
            except Exception as err:
                print(f"⚠️ [LLM PROVIDER FALLBACK]: OpenRouter API failed ({err}). Switching to Local Ollama...")

        # Tertiary #3: Local Ollama Model
        try:
            payload = {
                "model": self.local_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096}
            }
            resp = requests.post(self.local_llm_url, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"🤖 [LLM PROVIDER]: LOCAL LLM (Ollama - {self.local_model}) answered query!")
                return resp.json().get("response", "").strip()
            else:
                print(f"⚠️ Local Ollama returned status {resp.status_code}")
        except Exception as local_err:
            print(f"⚠️ Local LLM unreachable: {local_err}")

        return "Error: All LLM providers (Groq, OpenRouter, and Local Ollama) failed to respond."

    @traceable(name="tool_retrieve_context")
    def retrieve_context(self, query: str, top_k: int = 5, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tool: Retrieves top-k hybrid chunks (Dense Vector + BM25 Lexical + RRF)."""
        return self.retriever.search(query=query, top_k=top_k, session_id=session_id)

    @traceable(name="tool_extract_structured_json")
    def extract_structured_json(self, user_request: str, chunks: List[Dict[str, Any]]) -> StructuredExtractionSchema:
        """Tool: Extracts structured JSON data with self-correction validation loop."""
        context_str = "\n\n".join([f"--- Page {c['page_numbers']} ---\n{c['content']}" for c in chunks])
        prompt = STRUCTURED_EXTRACTION_PROMPT.format(context_str=context_str, user_request=user_request)

        raw_output = self._call_llm(prompt)
        
        # Self-Repair Loop if JSON schema validation fails
        try:
            cleaned = raw_output.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            return StructuredExtractionSchema(**data)
        except Exception as e:
            # Self-repair prompt call
            repair_prompt = SELF_REPAIR_PROMPT.format(malformed_output=raw_output, error_message=str(e))
            repaired_output = self._call_llm(repair_prompt)
            try:
                cleaned = repaired_output.strip().strip("```json").strip("```").strip()
                data = json.loads(cleaned)
                return StructuredExtractionSchema(**data)
            except Exception:
                return StructuredExtractionSchema(
                    document_title="Extraction Error",
                    extracted_fields=[]
                )

    @traceable(name="tool_summarize_document_section")
    def summarize_document_section(self, chunks: List[Dict[str, Any]]) -> str:
        """Tool: Generates executive Markdown summary across retrieved document section chunks."""
        context_str = "\n\n".join([f"--- Section: {c['section_path']} (Pages: {c['page_numbers']}) ---\n{c['content']}" for c in chunks])
        prompt = SECTION_SUMMARIZATION_PROMPT.format(context_str=context_str)
        return self._call_llm(prompt)
