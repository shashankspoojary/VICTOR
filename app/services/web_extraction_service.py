# app/services/web_extraction_service.py
import json
from pathlib import Path
from typing import Dict, Any
from playwright.async_api import Page
from config import BASE_DIR
from app.utils.extraction_utils import html_to_clean_markdown

class WebExtractionService:
    """Performs deep parsing extractions on functional text elements inside active contexts."""
    
    def __init__(self):
        self.default_output_root = BASE_DIR / "workspace" / "extracted_web_content"
        self.default_output_root.mkdir(parents=True, exist_ok=True)

    async def extract_and_save_page(self, page: Page, filename_slug: str, custom_path: str = None) -> Dict[str, Any]:
        """Extracts text structures and saves them as markdown files in default or custom directories."""
        try:
            url = page.url
            title = await page.title()
            raw_html = await page.content()
            
            markdown_content = html_to_clean_markdown(raw_html)
            
            # Determine output directory
            if custom_path and custom_path.strip() and custom_path.lower() != "none":
                output_dir = Path(custom_path.strip())
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = self.default_output_root
                
            target_path = output_dir / f"{filename_slug}.md"
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(f"--- \nURL: {url}\nTITLE: {title}\n---\n\n")
                f.write(markdown_content)
                
            return {
                "success": True,
                "title": title,
                "saved_path": str(target_path),
                "char_count": len(markdown_content),
                # ADDED: Send a chunk of the text back so the AI can read and summarize it
                "content_snippet": markdown_content[:2500] 
            }
        except Exception as e:
            return {"success": False, "error": f"Web scraping extraction failure: {str(e)}"}