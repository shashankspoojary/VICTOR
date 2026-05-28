# app/services/smart_navigation_service.py
from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from app.services.webpage_analysis_service import WebpageAnalysisService

class SmartNavigationService:
    """Heuristically ranks actionable items in active viewport matrices to prioritize targets."""
    
    def __init__(self, analysis_service: WebpageAnalysisService):
        self.analysis_service = analysis_service

    async def discover_best_match(self, page: Page, search_intent_keywords: List[str]) -> Optional[str]:
        """Scans page configurations to match actionable selectors against semantic criteria."""
        analysis_report = await self.analysis_service.parse_page_structure(page)
        if not analysis_report.get("success"):
            return None
            
        elements: List[Dict[str, Any]] = analysis_report.get("interactive_elements", [])
        best_selector: Optional[str] = None
        highest_score = 0
        
        for item in elements:
            score = 0
            text_context = (item.get("text", "") + " " + item.get("placeholder", "") + " " + item.get("name", "")).lower()
            
            for keyword in search_intent_keywords:
                if keyword.lower() in text_context:
                    score += 10
                    
            if score > highest_score:
                highest_score = score
                # Build valid selector matching strategy context
                if item["tag"] == "a" and item.get("href"):
                    best_selector = f"a[href='{item['href']}']"
                elif item.get("name"):
                    best_selector = f"{item['tag']}[name='{item['name']}']"
                    
        return best_selector