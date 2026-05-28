# app/utils/browser_utils.py
from typing import Dict, Any

def get_default_viewport() -> Dict[str, int]:
    """Returns standard high-definition viewport dimensions for Playwright configurations."""
    return {"width": 1280, "height": 720}

def get_chrome_user_agent() -> str:
    """Returns a modern, valid user-agent string to mimic standard web traffic profiles."""
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

def compile_browser_args() -> list[str]:
    """Generates standard performance and isolation argument flags for browser launching."""
    return [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--window-size=1280,720"
    ]