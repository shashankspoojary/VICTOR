# app/services/browser_navigation_service.py
from typing import Optional, List
from playwright.async_api import Page, BrowserContext
from app.services.browser_service import BrowserService
from app.services.browser_memory_service import BrowserMemoryService

class BrowserNavigationService:
    """Orchestrates high-level tab handling, explicit URL routing, and page interaction triggers."""
    
    def __init__(self, browser_service: BrowserService, memory_service: BrowserMemoryService):
        self.browser_service = browser_service
        self.memory_service = memory_service

    async def get_active_page(self, context: Optional[BrowserContext] = None) -> Page:
        """Retrieves the active page or creates a new one within the structural context layer."""
        ctx = context if context else await self.browser_service.get_context()
        pages = ctx.pages
        if pages:
            return pages[0]
        return await ctx.new_page()

    async def navigate_to_url(self, url: str, timeout_ms: int = 30000) -> Optional[Page]:
        """Routes the active browser interface to a target endpoint and waits for network stabilization."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            
        page = await self.get_active_page()
        try:
            await page.goto(url, timeout=timeout_ms, wait_until="load")
            await page.wait_for_timeout(1000)
            
            # Extract page title and log event to telemetry
            title = await page.title()
            self.memory_service.log_navigation_event(url, title, "SUCCESS")
            
            return page
        except Exception as e:
            print(f"[BrowserNavigationService Error] Navigation failed: {e}")
            self.memory_service.log_navigation_event(url, "Unknown Title", f"FAILED: {str(e)}")
            return None