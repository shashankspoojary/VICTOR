import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import logging
from typing import List, Dict, Any

import config
from app.utils.key_rotation import tavily_rotator
from tavily import TavilyClient

class RealtimeService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def search_web(self, query: str, max_results: int = 5) -> dict:
        for _ in range(len(tavily_rotator.keys)):
            try:
                key = tavily_rotator.get_key()
                client = TavilyClient(api_key=key)
                result = client.search(query=query, max_results=max_results, search_depth="advanced")
                return result
            except Exception as e:
                self.logger.warning(f"Search failed: {e}")
                tavily_rotator.rotate()
        
        return {"query": query, "results": [], "answer": "Search currently unavailable."}

    def get_search_context(self, query: str) -> str:
        search_result = self.search_web(query)
        results = search_result.get("results", [])
        
        context_parts = []
        for item in results:
            title = item.get('title', 'Unknown Title')
            url = item.get('url', 'Unknown URL')
            content = item.get('content', '')
            context_parts.append(f"Title: {title}\nURL: {url}\nContent: {content}\n")
            
        return "\n".join(context_parts)

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    logging.basicConfig(level=logging.INFO)
    service = RealtimeService()
    query = "Latest space exploration news 2026"
    print(f"Executing web search for: '{query}'")
    context = service.get_search_context(query)
    print("\n--- Context Chunks ---\n")
    print(context)
    print("\n--- Search Test Completed ---")
