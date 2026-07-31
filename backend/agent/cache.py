from typing import Dict, Any, Optional
from collections import OrderedDict

class QueryResponseCache:
    """
    In-Memory LRU Cache storing exact user queries, intent classifications,
    retrieved citations, and generated answers for sub-millisecond repeated responses.
    """
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached response if key exists."""
        clean_key = query.strip().lower()
        if clean_key in self._cache:
            self._cache.move_to_end(clean_key)
            return self._cache[clean_key]
        return None

    def put(self, query: str, intent: str, answer: str, citations: list, extracted_data: Optional[Dict[str, Any]] = None):
        """Stores query response in LRU cache."""
        clean_key = query.strip().lower()
        if clean_key in self._cache:
            self._cache.move_to_end(clean_key)
        self._cache[clean_key] = {
            "intent": intent,
            "answer": answer,
            "citations": citations,
            "extracted_data": extracted_data,
            "cached": True
        }
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

# Global singleton query cache
query_cache = QueryResponseCache()
