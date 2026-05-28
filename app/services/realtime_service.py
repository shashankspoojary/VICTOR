import httpx
from app.utils.retry import async_retry
from app.utils.key_rotation import tavily_key_manager

class RealtimeService:
    def __init__(self):
        self.base_url = "https://api.tavily.com/search"

    @async_retry(max_retries=3)
    async def search(self, query: str) -> str:
        """Performs a real-time web search with automatic API key rotation."""
        current_key = tavily_key_manager.get_current_key()
            
        payload = {
            "api_key": current_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 3
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, json=payload, timeout=10.0)
            
            # If rate limited (429) or key is dead (401/403), trigger rotation
            if response.status_code in (429, 401, 403):
                tavily_key_manager.rotate_key()
                response.raise_for_status() # This forces the @async_retry decorator to fire
                
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("answer")
            if answer:
                return answer
                
            results = data.get("results", [])
            if not results:
                return "No web results found."
                
            summaries = [f"- {r.get('title')}: {r.get('content')}" for r in results]
            return "\n".join(summaries)