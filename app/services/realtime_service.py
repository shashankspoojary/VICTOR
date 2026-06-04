import aiohttp
import logging
from app.utils.retry import async_retry
from app.utils.key_rotation import tavily_key_manager

logger = logging.getLogger(__name__)

class RealtimeService:
    @async_retry(retries=3, key_manager=tavily_key_manager)
    async def search_web(self, query: str, max_results: int = 5) -> str:
        api_key = tavily_key_manager.get_current_key()
        if not api_key:
            raise ValueError("No active Tavily API key available.")
        
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_raw_content": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Tavily API error ({response.status}): {text}")
                
                data = await response.json()
                results = data.get("results", [])
                
                if not results:
                    return "No results found."
                
                formatted_results = []
                for res in results:
                    title = res.get("title", "No Title")
                    url_val = res.get("url", "No URL")
                    content = res.get("content", "No Content")
                    formatted_results.append(f"Source: [{title}] - {url_val}\nSnippet: {content}\n---")
                    
                return "\n".join(formatted_results)
