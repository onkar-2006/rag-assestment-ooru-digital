import json
import requests
from typing import List, Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from backend.agent.hybrid_retriever import HybridRetriever
from backend.agent.tools import AgentTools
from backend.agent.prompt import INTENT_ROUTER_PROMPT, GROUNDED_QA_PROMPT
from backend.agent.models import Citation, AgentResponse
from backend.config import config

from backend.guardrails import InputGuardrail, OutputGuardrail

class AgentGraphState(TypedDict):
    """LangGraph State Schema holding conversational trajectory."""
    messages: List[Dict[str, str]]
    query: str
    session_id: Optional[str]
    intent: str
    chunks: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    final_answer: str
    extracted_json: Optional[Dict[str, Any]]
    guardrail_blocked: bool


from backend.agent.cache import query_cache

class LangGraphDocumentWorkflow:
    """
    Production LangGraph Workflow Engine.
    Handles Fast Intent Router classification, Casual greeting bypass, Hybrid tool retrieval,
    Query Response Caching, and Grounded Guardrail response synthesis.
    """
    def __init__(self, hybrid_retriever: Optional[HybridRetriever] = None):
        self.retriever = hybrid_retriever or HybridRetriever()
        self.tools = AgentTools(self.retriever)
        self.input_guardrail = InputGuardrail()
        self.output_guardrail = OutputGuardrail()
        self.groq_llm = None
        self.fast_router_llm = None

        if config.groq_api_key:
            try:
                self.groq_llm = ChatGroq(
                    groq_api_key=config.groq_api_key,
                    model_name=config.groq_model,
                    temperature=0.0
                )
            except Exception:
                self.groq_llm = None

        # Fast small model for intent routing (ChatGroq llama-3.1-8b-instant / llama-3.3-70b)
        self.router_groq_llm = None
        if config.groq_api_key:
            try:
                self.router_groq_llm = ChatGroq(
                    groq_api_key=config.groq_api_key,
                    model_name=config.router_model if "llama" in config.router_model else config.groq_model,
                    temperature=0.0
                )
            except Exception:
                self.router_groq_llm = self.groq_llm

        self.workflow = self._build_graph()


    def input_guardrail_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Scans input query for prompt injection or malicious patterns."""
        query = state["query"]
        guard_res = self.input_guardrail.validate_input(query)
        if not guard_res.is_safe:
            state["guardrail_blocked"] = True
            state["final_answer"] = f"⚠️ Security Warning: {guard_res.reasoning}"
            state["intent"] = "blocked"
            state["citations"] = []
        else:
            state["guardrail_blocked"] = False
        return state

    def output_guardrail_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Validates output answer against retrieved context chunks for hallucinations."""
        if state.get("guardrail_blocked", False) or state.get("intent") in ["greeting", "blocked"]:
            return state

        answer = state.get("final_answer", "")
        chunks = state.get("chunks", [])

        out_res = self.output_guardrail.validate_output(answer, chunks)
        if not out_res.is_faithful:
            state["final_answer"] = "I am unable to find relevant information in the provided document to answer your question."
            state["citations"] = []

        return state


    def _call_router_llm(self, user_query: str) -> Dict[str, str]:
        """Classifies intent via ChatGroq fast low-latency model (~150ms classification)."""
        prompt = INTENT_ROUTER_PROMPT.format(user_input=user_query)
        content = ""

        # 1. Try ChatGroq fast router model first
        if self.router_groq_llm or self.groq_llm:
            try:
                llm = self.router_groq_llm or self.groq_llm
                res = llm.invoke(prompt)
                content = str(res.content).strip()
            except Exception:
                pass

        # 2. Fallback to ChatOpenAI via OpenRouter if Groq is unavailable
        if not content and config.openrouter_api_key:
            try:
                from langchain_openai import ChatOpenAI
                router_llm = ChatOpenAI(
                    openai_api_key=config.openrouter_api_key,
                    openai_api_base=config.openrouter_base_url,
                    model_name=config.router_model,
                    temperature=0.0
                )
                res = router_llm.invoke(prompt)
                content = str(res.content).strip()
            except Exception:
                return {"intent": "document_qa", "reasoning": "Fallback to RAG"}

        if not content:
            return {"intent": "document_qa", "reasoning": "Fallback to RAG"}

        try:
            clean_str = content.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_str)
        except Exception:
            return {"intent": "document_qa", "reasoning": "Fallback to RAG"}



    def intent_router_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Classifies intent into greeting, document_qa, structured_extraction, or summarization."""
        query = state["query"]
        router_res = self._call_router_llm(query)
        intent = router_res.get("intent", "document_qa")
        state["intent"] = intent
        return state

    def direct_conversational_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Bypasses tool retrieval for casual greetings."""
        state["final_answer"] = "Hello! I am your Agentic Document Intelligence Assistant. How can I help you analyze your documents today?"
        state["citations"] = []
        return state

    def hybrid_retrieval_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Executes Hybrid Dense + BM25 + RRF Retrieval."""
        query = state["query"]
        session_id = state.get("session_id")
        chunks = self.tools.retrieve_context(query, limit=config.hybrid_top_k, session_id=session_id)
        state["chunks"] = chunks
        
        citations = []
        for c in chunks:
            citations.append({
                "doc_name": c.get("doc_name", "Unknown"),
                "page_numbers": c.get("page_numbers", []),
                "section_path": c.get("section_path", "General"),
                "chunk_id": c.get("chunk_id", ""),
                "score": float(c.get("rrf_score", c.get("score", 0.0)))
            })
        state["citations"] = citations
        return state



    def structured_extraction_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Extracts validated Pydantic JSON schema."""
        query = state["query"]
        chunks = state.get("chunks", [])
        if not chunks:
            chunks = self.tools.retrieve_context(query, limit=config.hybrid_top_k)
            state["chunks"] = chunks
            
        extracted_data = self.tools.extract_structured_json(query, chunks)
        state["extracted_json"] = extracted_data
        state["final_answer"] = f"```json\n{json.dumps(extracted_data, indent=2)}\n```"
        return state

    def summarization_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Executes section map-reduce summarization."""
        query = state["query"]
        chunks = state.get("chunks", [])
        if not chunks:
            chunks = self.tools.retrieve_context(query, limit=config.hybrid_top_k)
            state["chunks"] = chunks
            
        summary = self.tools.summarize_document_section(query, chunks)
        state["final_answer"] = summary
        return state

    def cross_doc_comparison_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Executes Multi-Document / Cross-Document Reasoning."""
        query = state["query"]
        chunks = state.get("chunks", [])

        if not chunks:
            state["final_answer"] = "I am unable to find relevant information across the provided documents to compare."
            return state

        context_str = "\n\n".join([f"--- Document: {c['doc_name']} | Chunk ID: {c['chunk_id']} (Section: {c['section_path']}, Pages: {c['page_numbers']}) ---\n{c['content']}" for c in chunks])
        from backend.agent.prompt import CROSS_DOCUMENT_REASONING_PROMPT
        prompt = CROSS_DOCUMENT_REASONING_PROMPT.format(context_str=context_str, query=query)
        
        state["final_answer"] = self.tools._call_llm(prompt)
        return state

    def grounded_qa_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Synthesizes grounded answers with citations."""
        query = state["query"]
        chunks = state.get("chunks", [])

        if not chunks:
            state["final_answer"] = "I am unable to find relevant information in the provided document to answer your question."
            return state

        context_str = "\n\n".join([f"--- Chunk ID: {c['chunk_id']} (Section: {c['section_path']}, Pages: {c['page_numbers']}) ---\n{c['content']}" for c in chunks])
        prompt = GROUNDED_QA_PROMPT.format(context_str=context_str, query=query)
        
        state["final_answer"] = self.tools._call_llm(prompt)
        return state

    def _route_input_guard(self, state: AgentGraphState) -> str:
        """Route based on input guardrail scan."""
        if state.get("guardrail_blocked", False):
            return "blocked"
        return "passed"

    def _route_next(self, state: AgentGraphState) -> str:
        """Conditional Edge Router."""
        intent = state.get("intent", "document_qa")
        if intent == "greeting":
            return "direct_chat"
        elif intent == "structured_extraction":
            return "hybrid_retrieve_then_extract"
        elif intent == "summarization":
            return "hybrid_retrieve_then_summarize"
        elif intent == "cross_doc_comparison":
            return "hybrid_retrieve_then_cross_doc"
        else:
            return "hybrid_retrieve_then_qa"

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentGraphState)

        # Add Nodes
        builder.add_node("input_guardrail", self.input_guardrail_node)
        builder.add_node("router", self.intent_router_node)
        builder.add_node("direct_chat", self.direct_conversational_node)
        builder.add_node("hybrid_retrieval", self.hybrid_retrieval_node)
        builder.add_node("grounded_qa", self.grounded_qa_node)
        builder.add_node("cross_doc_comparison", self.cross_doc_comparison_node)
        builder.add_node("structured_extraction", self.structured_extraction_node)
        builder.add_node("summarizer", self.summarization_node)
        builder.add_node("output_guardrail", self.output_guardrail_node)

        # Entry point: Scan input query through Input Guardrail
        builder.set_entry_point("input_guardrail")

        # Route after Input Guardrail
        builder.add_conditional_edges(
            "input_guardrail",
            self._route_input_guard,
            {
                "blocked": END,
                "passed": "router"
            }
        )

        # Conditional routing after router
        builder.add_conditional_edges(
            "router",
            self._route_next,
            {
                "direct_chat": "direct_chat",
                "hybrid_retrieve_then_extract": "hybrid_retrieval",
                "hybrid_retrieve_then_summarize": "hybrid_retrieval",
                "hybrid_retrieve_then_cross_doc": "hybrid_retrieval",
                "hybrid_retrieve_then_qa": "hybrid_retrieval"
            }
        )

        # Route after retrieval
        def _after_retrieval_route(state: AgentGraphState) -> str:
            intent = state.get("intent", "document_qa")
            if intent == "structured_extraction":
                return "structured_extraction"
            elif intent == "summarization":
                return "summarizer"
            elif intent == "cross_doc_comparison":
                return "cross_doc_comparison"
            return "grounded_qa"

        builder.add_conditional_edges(
            "hybrid_retrieval",
            _after_retrieval_route,
            {
                "structured_extraction": "structured_extraction",
                "summarizer": "summarizer",
                "cross_doc_comparison": "cross_doc_comparison",
                "grounded_qa": "grounded_qa"
            }
        )

        # Output nodes route through Output Guardrail before ending
        builder.add_edge("grounded_qa", "output_guardrail")
        builder.add_edge("cross_doc_comparison", "output_guardrail")
        builder.add_edge("structured_extraction", "output_guardrail")
        builder.add_edge("summarizer", "output_guardrail")

        builder.add_edge("direct_chat", END)
        builder.add_edge("output_guardrail", END)

        return builder.compile()



    def run(self, user_query: str, history: Optional[List[Dict[str, str]]] = None, session_id: Optional[str] = None) -> AgentResponse:
        """Executes the state graph for a user prompt with LRU response caching isolated by session_id."""
        cache_key = f"{session_id}:{user_query}" if session_id else user_query
        # 1. Check LRU Response Cache for exact repeated queries (<1ms response, $0.00 cost)
        cached = query_cache.get(cache_key)
        if cached:
            citations_models = [Citation(**c) for c in cached.get("citations", [])]
            return AgentResponse(
                answer=cached["answer"],
                intent=cached["intent"],
                citations=citations_models,
                extracted_data=cached.get("extracted_data")
            )

        # 2. Execute LangGraph State Graph Workflow
        initial_state: AgentGraphState = {
            "messages": history or [],
            "query": user_query,
            "session_id": session_id,
            "intent": "",
            "chunks": [],
            "citations": [],
            "final_answer": "",
            "extracted_json": None,
            "guardrail_blocked": False
        }

        final_state = self.workflow.invoke(initial_state)
        
        citations_models = [Citation(**c) for c in final_state.get("citations", [])]
        
        # 3. Store response in LRU Cache
        if not final_state.get("guardrail_blocked", False) and final_state.get("intent") != "blocked":
            query_cache.put(
                query=cache_key,
                intent=final_state["intent"],
                answer=final_state["final_answer"],
                citations=final_state.get("citations", []),
                extracted_data=final_state.get("extracted_json")
            )

        return AgentResponse(
            answer=final_state["final_answer"],
            intent=final_state["intent"],
            citations=citations_models,
            extracted_data=final_state.get("extracted_json")
        )



