import os
from pydantic import BaseModel

class AppConfig(BaseModel):
    # Qdrant Cloud Credentials
    qdrant_url: str = os.getenv("QDRANT_URL", "https://bb03db18-09fc-41fb-a3d6-9a3fa3d0a360.eu-west-1-0.aws.cloud.qdrant.io")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    collection_name: str = os.getenv("QDRANT_COLLECTION", "document_intelligence_chunks")

    # Groq & OpenRouter Credentials
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # LLM & Router Model Settings
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    router_model: str = os.getenv("ROUTER_MODEL", "llama-3.1-8b-instant")

    # LangSmith Observability & Tracing Credentials
    langchain_tracing_v2: str = os.getenv("LANGCHAIN_TRACING_V2", "true")
    langchain_endpoint: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    langchain_api_key: str = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "rag-observebility")

    # Hybrid Retrieval & RRF Hyperparameters
    rrf_k: int = 60
    hybrid_top_k: int = 5

    # Chunker Hyperparameters
    target_max_tokens: int = 450
    overlap_tokens: int = 40

# Automatically set environment variables for LangSmith automatic tracing
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "rag-observebility")

config = AppConfig()



