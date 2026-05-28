# app/utils/html_utils.py
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

def clean_html_boilerplate(raw_html: str) -> str:
    """Strips high-noise boilerplate markup like scripts, styles, metadata, and comments."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for element in soup(["script", "style", "meta", "link", "noscript", "svg", "iframe"]):
        element.decompose()
    return str(soup)

def extract_interactive_elements(raw_html: str) -> List[Dict[str, Any]]:
    """Statically parses an HTML blob to find interactive components like fields, inputs, and links."""
    elements = []
    if not raw_html:
        return elements
        
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # Track input fields
    for index, item in enumerate(soup.find_all(["input", "textarea", "button", "select"])):
        elements.append({
            "id": f"input_{index}",
            "tag": item.name,
            "type": item.get("type", "text"),
            "name": item.get("name", ""),
            "placeholder": item.get("placeholder", ""),
            "value": item.get("value", ""),
            "text": item.get_text(strip=True)[:100]
        })
        
    # Track hypermedia anchors
    for index, anchor in enumerate(soup.find_all("a", href=True)):
        href = anchor.get("href")
        text = anchor.get_text(strip=True)
        if href and (href.startswith("http") or href.startswith("/")):
            elements.append({
                "id": f"link_{index}",
                "tag": "a",
                "href": href,
                "text": text[:100] if text else "[Image/Empty Link]"
            })
            
    return elements