# app/services/browser_session_service.py
import json
from pathlib import Path
from typing import Optional
from playwright.async_api import BrowserContext
from config import BASE_DIR
from app.services.browser_service import BrowserService

class BrowserSessionService:
    """Manages authentication states, storage footprints, cookies, and local data persistence profiles."""
    
    def __init__(self, browser_service: BrowserService):
        self.browser_service = browser_service
        self.sessions_root = BASE_DIR / "workspace" / "browser_sessions"
        self.sessions_root.mkdir(parents=True, exist_ok=True)

    def _get_profile_path(self, session_id: str) -> Path:
        return self.sessions_root / f"state_{session_id}.json"

    async def create_persisted_context(self, session_id: str) -> BrowserContext:
        """Spins up a new contextual sandbox using authenticated storage profile maps if available."""
        browser = await self.browser_service.initialize_browser()
        profile_path = self._get_profile_path(session_id)
        
        # Check configuration track
        if profile_path.exists() and profile_path.stat().st_size > 0:
            context = await browser.new_context(
                storage_state=str(profile_path),
                ignore_https_errors=True
            )
            return context
            
        # Fallback to dynamic context allocation if record profile isn't active yet
        return await self.browser_service.get_context()

    async def save_session_state(self, session_id: str, context: BrowserContext) -> bool:
        """Captures cookies and local storage states from the active instance to a file."""
        try:
            profile_path = self._get_profile_path(session_id)
            await context.storage_state(path=str(profile_path))
            return True
        except Exception:
            return False

    async def clear_session_profile(self, session_id: str) -> bool:
        """Removes the stored session file from disk."""
        profile_path = self._get_profile_path(session_id)
        if profile_path.exists():
            profile_path.unlink()
            return True
        return False