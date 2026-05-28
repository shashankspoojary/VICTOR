# app/utils/extraction_utils.py
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

def html_to_clean_markdown(raw_html: str) -> str:
    """Converts structural HTML containers into readable, tabular markdown representations."""
    if not raw_html:
        return "Empty document."
        
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # Process text layout boundaries
    for header in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(header.name[1])
        header.replace_with(f"\n\n{'#' * level} {header.get_text(strip=True)}\n")
        
    for p in soup.find_all("p"):
        p.replace_with(f"\n{p.get_text(strip=True)}\n")
        
    for br in soup.find_all("br"):
        br.replace_with("\n")
        
    text = soup.get_text()
    # Normalize excessive multi-line spacing breaks
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def filter_relevant_snippets(text: str, focus_keywords: List[str]) -> str:
    """Isolates specific functional paragraphs within large bodies of text matching an asset list."""
    if not text or not focus_keywords:
        return text[:2000] # Return safe default buffer if no target constraint defined
        
    paragraphs = text.split("\n\n")
    matching_blocks = []
    
    for para in paragraphs:
        if any(kw.lower() in para.lower() for kw in focus_keywords):
            matching_blocks.append(para.strip())
            
    if not matching_blocks:
        return text[:1500]
        
    return "\n\n---\n\n".join(matching_blocks[:10])