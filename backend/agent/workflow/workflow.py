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
    Master Production LangGraph Agent Workflow Engine.
    Orchestrates execution across state nodes:
    1. Input Guardrail Verification
    2. Fast Intent Classification & Query Routing
    3. Hybrid Retrieval (Dense Vector + BM25 Lexical + RRF Reranking)
    4. Task Execution Nodes (Grounded QA, Structured Extraction, Section Summarizer, Direct Chat)
    5. Output Faithfulness Guardrail Verification
    """
    def __init__(self, hybrid_retriever: Optional[HybridRetriever] = None):
        self.retriever = hybrid_retriever or HybridRetriever()
        self.tools = AgentTools(self.retriever)
        self.input_guardrail = InputGuardrail()
        self.output_guardrail = OutputGuardrail()

        # Initialize Groq router LLM for fast intent classification
        self.router_llm = None
        if config.groq_api_key:
            try:
                self.router_llm = ChatGroq(
                    groq_api_key=config.groq_api_key,
                    model_name="llama-3.1-8b-instant",
                    temperature=0.0
                )
            except Exception as e:
                print(f"⚠️ Fast Router ChatGroq init error: {e}")

        # Build State Graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Constructs LangGraph State Machine with conditional edges."""
        workflow = StateGraph(AgentGraphState)

        # Register State Nodes
        workflow.add_node("input_guardrail", self.input_guardrail_node)
        workflow.add_node("intent_router", self.intent_router_node)
        workflow.add_node("hybrid_retriever", self.retrieval_node)
        workflow.add_node("direct_response", self.direct_response_node)
        workflow.add_node("grounded_qa", self.grounded_qa_node)
        workflow.add_node("structured_extraction", self.structured_extraction_node)
        workflow.add_node("summarization", self.summarization_node)
        workflow.add_node("cross_doc_comparison", self.cross_doc_comparison_node)
        workflow.add_node("output_guardrail", self.output_guardrail_node)

        # Define Execution Graph Connections
        workflow.set_entry_point("input_guardrail")

        # Conditional Edge after Input Guardrail
        workflow.add_conditional_edges(
            "input_guardrail",
            self.check_input_guardrail,
            {
                "blocked": END,
                "passed": "intent_router"
            }
        )

        # Conditional Edge after Intent Classification Router
        workflow.add_conditional_edges(
            "intent_router",
            self.route_intent,
            {
                "greeting": "direct_response",
                "document_qa": "hybrid_retriever",
                "structured_extraction": "hybrid_retriever",
                "summarization": "hybrid_retriever",
                "cross_doc_comparison": "hybrid_retriever"
            }
        )

        # Conditional Edge after Retrieval Node to execution tools
        workflow.add_conditional_edges(
            "hybrid_retriever",
            self.route_retrieved_task,
            {
                "document_qa": "grounded_qa",
                "structured_extraction": "structured_extraction",
                "summarization": "summarization",
                "cross_doc_comparison": "cross_doc_comparison"
            }
        )

        # Execution nodes converge to Output Guardrail Verification
        workflow.add_edge("direct_response", "output_guardrail")
        workflow.add_edge("grounded_qa", "output_guardrail")
        workflow.add_edge("structured_extraction", "output_guardrail")
        workflow.add_edge("summarization", "output_guardrail")
        workflow.add_edge("cross_doc_comparison", "output_guardrail")
        workflow.add_edge("output_guardrail", END)

        # Compile graph with LangGraph MemorySaver checkpointer (InMemorySaver) for state persistence
        from langgraph.checkpoint.memory import MemorySaver
        self.checkpointer = MemorySaver()
        return workflow.compile(checkpointer=self.checkpointer)




    # --- LangGraph Node Functions ---

    def input_guardrail_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Validates query against prompt injection and security rules."""
        query = state["query"]
        decision = self.input_guardrail.validate_input(query)

        if not decision.is_safe:
            state["guardrail_blocked"] = True
            state["final_answer"] = f"⚠️ [SECURITY GUARDRAIL TRIGGERED]: {decision.reasoning}"
            state["intent"] = "security_blocked"
        else:
            state["guardrail_blocked"] = False

        return state


    def check_input_guardrail(self, state: AgentGraphState) -> str:
        """Edge Assessor: Routes to END if input guardrail blocked query."""
        return "blocked" if state.get("guardrail_blocked", False) else "passed"

    def intent_router_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Classifies query intent ('greeting', 'document_qa', 'structured_extraction', 'summarization', 'cross_doc_comparison')."""
        query = state["query"]

        # Fast heuristic checks for obvious intents
        query_lower = query.strip().lower()
        if query_lower in ["hi", "hello", "hey", "who are you", "what can you do", "thanks", "thank you"]:
            state["intent"] = "greeting"
            return state

        # Prompt LLM Intent Classifier
        prompt = INTENT_ROUTER_PROMPT.format(user_input=query)
        intent = "document_qa" # default

        if self.router_llm:
            try:
                resp = self.router_llm.invoke(prompt)
                cleaned = resp.content.strip().strip("```json").strip("```").strip()
                parsed = json.loads(cleaned)
                intent = parsed.get("intent", "document_qa")
            except Exception as err:
                print(f"⚠️ Fast router failed ({err}). Defaulting intent to 'document_qa'")

        # Fallback keyword checks if router is uncertain
        if any(k in query_lower for k in ["extract", "json", "key value", "table", "schema", "dates"]):
            intent = "structured_extraction"
        elif any(k in query_lower for k in ["summarize", "summary", "overview", "key points", "synopsis"]):
            intent = "summarization"
        elif any(k in query_lower for k in ["compare", "difference between", "versus", "vs", "contrast"]):
            intent = "cross_doc_comparison"

        state["intent"] = intent
        return state

    def route_intent(self, state: AgentGraphState) -> str:
        """Edge Assessor: Routes state graph based on intent."""
        return state.get("intent", "document_qa")

    def direct_response_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Handles casual greetings directly without document retrieval."""
        query = state["query"]
        prompt = f"You are an Agentic Document Intelligence Assistant. Respond politely and concisely to this user greeting: '{query}'"
        answer = self.tools._call_llm(prompt)
        state["final_answer"] = answer
        state["citations"] = []
        return state

    def retrieval_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Performs Hybrid Context Retrieval (Dense + BM25 + RRF)."""
        query = state["query"]
        session_id = state.get("session_id")
        
        # Retrieve top 5 hybrid reranked context chunks isolated by session_id
        hybrid_chunks = self.tools.retrieve_context(query, top_k=5, session_id=session_id)
        
        state["chunks"] = hybrid_chunks
        
        # Format citations
        citations = []
        for c in hybrid_chunks:
            citations.append({
                "doc_name": c.get("doc_name", "Document"),
                "page_numbers": c.get("page_numbers", []),
                "section_path": c.get("section_path", "Main"),
                "chunk_id": c.get("chunk_id", ""),
                "score": c.get("rrf_score", c.get("score", 0.0))
            })
        state["citations"] = citations
        return state

    def route_retrieved_task(self, state: AgentGraphState) -> str:
        """Edge Assessor: Routes retrieved context to task node."""
        return state.get("intent", "document_qa")

    def cross_doc_comparison_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Performs reasoning across multiple uploaded documents."""
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
            state["final_answer"] = "I am unable to answer this question based on the provided document context."
            return state

        context_str = "\n\n".join([f"--- Section: {c['section_path']} (Pages: {c['page_numbers']}) ---\n{c['content']}" for c in chunks])
        prompt = GROUNDED_QA_PROMPT.format(context_str=context_str, query=query)
        
        answer = self.tools._call_llm(prompt)
        state["final_answer"] = answer
        return state

    def structured_extraction_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Extracts structured JSON with Pydantic self-repair reflection loop."""
        query = state["query"]
        chunks = state.get("chunks", [])

        if not chunks:
            state["final_answer"] = "No relevant context found to extract structured data."
            state["extracted_json"] = {}
            return state

        result_schema = self.tools.extract_structured_json(user_request=query, chunks=chunks)
        state["extracted_json"] = result_schema.model_dump()
        state["final_answer"] = f"Successfully extracted structured data from document context:\n```json\n{json.dumps(result_schema.model_dump(), indent=2)}\n```"
        return state

    def summarization_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Generates section-aware map-reduce Markdown summary."""
        chunks = state.get("chunks", [])

        if not chunks:
            state["final_answer"] = "No document section context available to summarize."
            return state

        summary = self.tools.summarize_document_section(chunks=chunks)
        state["final_answer"] = summary
        return state

    def output_guardrail_node(self, state: AgentGraphState) -> AgentGraphState:
        """LangGraph Node: Verifies output faithfulness and grounding to prevent hallucination."""
        answer = state.get("final_answer", "")
        chunks = state.get("chunks", [])
        intent = state.get("intent", "")

        # Skip verification for greetings or blocked queries
        if intent in ["greeting", "security_blocked"] or not chunks:
            return state

        decision = self.output_guardrail.validate_output(answer=answer, context_chunks=chunks)

        if not decision.is_faithful:
            print(f"⚠️ [OUTPUT GUARDRAIL WARNING]: {decision.reasoning}")
            # Append soft disclaimers if grounding overlap is low
            state["final_answer"] = f"{answer}\n\n_*Note: Some details in this response could not be strictly verified against source document text._"


        return state

    # --- Execution Method ---

    def run(self, query: str, history: Optional[List[Dict[str, str]]] = None, session_id: Optional[str] = None) -> AgentResponse:
        """
        Main Execution Endpoint: Runs LangGraph Workflow with LRU caching.
        """

        # 1. Check LRU Cache
        cached = query_cache.get(query)
        if cached:
            print(f"⚡ [CACHE HIT]: Returning sub-millisecond cached response for query: '{query}'")
            return AgentResponse(
                answer=cached["answer"],
                intent=cached["intent"],
                citations=[Citation(**c) for c in cached["citations"]],
                extracted_data=cached.get("extracted_data")
            )

        # 2. Initialize State
        initial_state: AgentGraphState = {
            "messages": [{"role": "user", "content": query}],
            "query": query,
            "session_id": session_id,
            "intent": "document_qa",
            "chunks": [],
            "citations": [],
            "final_answer": "",
            "extracted_json": None,
            "guardrail_blocked": False
        }

        # 3. Invoke LangGraph Workflow Engine with MemorySaver checkpointer persistence
        thread_config = {"configurable": {"thread_id": session_id or "default_session"}}
        final_state = self.graph.invoke(initial_state, config=thread_config)


        # 4. Format Output Schema
        citations = [Citation(**c) for c in final_state.get("citations", [])]
        response = AgentResponse(
            answer=final_state.get("final_answer", ""),
            intent=final_state.get("intent", "document_qa"),
            citations=citations,
            extracted_data=final_state.get("extracted_json")
        )

        # 5. Store in LRU Cache (if not blocked)
        if not final_state.get("guardrail_blocked", False):
            query_cache.put(
                query=query,
                intent=response.intent,
                answer=response.answer,
                citations=[c.model_dump() for c in response.citations],
                extracted_data=response.extracted_data
            )

        return response
