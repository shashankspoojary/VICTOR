# app/services/browser_service.py
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext
from app.utils.browser_utils import get_chrome_user_agent, get_default_viewport, compile_browser_args

class BrowserService:
    """Manages the lifecycle and automation configurations of the core system browser instance."""
    
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._primary_context: Optional[BrowserContext] = None

    # CHANGED: Reverted back to headless=True for invisible background execution
    async def initialize_browser(self, headless: bool = True) -> Browser:
        """Asynchronously triggers the initialization vectors for Playwright."""
        if self._browser:
            return self._browser
            
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=compile_browser_args()
        )
        return self._browser

    async def get_context(self) -> BrowserContext:
        """Retrieves or scopes an isolated operational context with customized configurations."""
        if not self._browser:
            await self.initialize_browser()
            
        if not self._primary_context:
            viewport = get_default_viewport()
            self._primary_context = await self._browser.new_context(
                viewport=viewport,
                user_agent=get_chrome_user_agent(),
                ignore_https_errors=True
            )
        return self._primary_context

    async def close_browser(self):
        """Performs a graceful teardown of active execution context blocks to reclaim system memory."""
        if self._primary_context:
            await self._primary_context.close()
            self._primary_context = None
            
        if self._browser:
            await self._browser.close()
            self._browser = None
            
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None