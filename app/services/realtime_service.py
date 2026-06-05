import asyncio
from tavily import AsyncTavilyClient
from app.utils.key_rotation import tavily_rotator
from app.utils.retry import with_retry_and_rotation

class RealtimeService:
    @with_retry_and_rotation(rotator=tavily_rotator, max_retries=3, base_delay=1.0)
    async def search(self, query: str) -> str:
        api_key = tavily_rotator.get_key()
        if not api_key:
            raise ValueError("No Tavily API key available.")
            
        client = AsyncTavilyClient(api_key=api_key)
        
        response = await client.search(query=query, search_depth="advanced")
        
        results = response.get('results', [])
        if not results:
            return "No results found."
            
        summary = ""
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No Title')
            content = res.get('content', 'No Content')
            url = res.get('url', '')
            summary += f"{i}. {title}\n{content}\nSource: {url}\n\n"
            
        return summary.strip()

realtime_service = RealtimeService()
