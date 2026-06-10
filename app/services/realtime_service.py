import asyncio
from tavily import AsyncTavilyClient
from app.utils.key_rotation import tavily_rotator
from app.utils.retry import with_retry_and_rotation

class RealtimeService:
    async def search(self, query: str) -> dict:
        # First, try DuckDuckGo as primary search
        try:
            results = await self._ddg_search(query)
            if results and results["results"]:
                return results
        except Exception as e:
            print(f"DDG Search failed: {e}")
            
        # Fallback to Tavily
        print("Falling back to Tavily search...")
        try:
            return await self._tavily_search(query)
        except Exception as e:
            print(f"Tavily Search failed: {e}")
            return {"summary": "No results found.", "results": []}

    async def _ddg_search(self, query: str) -> dict:
        from duckduckgo_search import DDGS
        import asyncio
        
        def run_ddgs():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=5))
                
        results = await asyncio.to_thread(run_ddgs)
        
        if not results:
            return {"summary": "No results found.", "results": []}
            
        summary = ""
        parsed_results = []
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No Title')
            content = res.get('body', 'No Content')
            url = res.get('href', '')
            summary += f"{i}. {title}\n{content}\nSource: {url}\n\n"
            parsed_results.append({
                "title": title,
                "content": content,
                "url": url,
                "score": 1.0
            })
            
        return {"summary": summary.strip(), "results": parsed_results}

    @with_retry_and_rotation(rotator=tavily_rotator, max_retries=3, base_delay=1.0)
    async def _tavily_search(self, query: str) -> dict:
        api_key = tavily_rotator.get_key()
        if not api_key:
            raise ValueError("No Tavily API key available.")

        client = AsyncTavilyClient(api_key=api_key)

        response = await asyncio.wait_for(
            client.search(query=query, search_depth="basic", max_results=5),
            timeout=8.0
        )

        results = response.get('results', [])
        if not results:
            return {"summary": "No results found.", "results": []}

        summary = ""
        parsed_results = []
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No Title')
            content = res.get('content', 'No Content')
            url = res.get('url', '')
            score = res.get('score', 0.0)
            summary += f"{i}. {title}\n{content}\nSource: {url}\n\n"
            parsed_results.append({
                "title": title,
                "content": content,
                "url": url,
                "score": score
            })

        return {"summary": summary.strip(), "results": parsed_results}

realtime_service = RealtimeService()
