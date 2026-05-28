# app/services/webpage_analysis_service.py
from typing import Dict, Any, List
from playwright.async_api import Page
from app.utils.html_utils import clean_html_boilerplate, extract_interactive_elements

class WebpageAnalysisService:
    """Statically parses and classifies live interface layouts to aid execution planning blocks."""
    
    def __init__(self):
        pass

    async def parse_page_structure(self, page: Page) -> Dict[str, Any]:
        """Inspects structural content layouts and evaluates structural node arrays."""
        try:
            title = await page.title()
            current_url = page.url
            raw_html = await page.content()
            
            cleaned_html = clean_html_boilerplate(raw_html)
            interactive_nodes = extract_interactive_elements(raw_html)
            
            return {
                "success": True,
                "title": title,
                "url": current_url,
                "metrics": {
                    "raw_length": len(raw_html),
                    "cleaned_length": len(cleaned_html),
                    "interactive_count": len(interactive_nodes)
                },
                "interactive_elements": interactive_nodes
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed structural DOM evaluation tracking: {str(e)}"
            }

    async def capture_element_bbox(self, page: Page, selector: str) -> Dict[str, float]:
        """Extracts localized layout positions for targeting peripheral simulation systems."""
        element = await page.query_selector(selector)
        if not element:
            return {}
        bbox = await element.bounding_box()
        return dict(bbox) if bbox else {}