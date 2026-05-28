# app/utils/code_utils.py
import ast
import re
from typing import List, Dict, Any

def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extracts code blocks along with their specified language from markdown text."""
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    matches = pattern.findall(text)
    blocks = []
    for lang, code in matches:
        blocks.append({
            "language": lang.strip().lower() or "text",
            "code": code.strip()
        })
    return blocks

def clean_python_code(text: str) -> str:
    """Removes markdown decorators and extracts raw code blocks if present."""
    blocks = extract_code_blocks(text)
    python_blocks = [b["code"] for b in blocks if b["language"] in ("python", "py")]
    if python_blocks:
        return "\n\n".join(python_blocks)
    
    # Fallback to scrubbing block tags if strings are returned poorly
    cleaned = re.sub(r"```(\w*)\n", "", text)
    cleaned = cleaned.replace("```", "")
    return cleaned.strip()

def validate_python_syntax(code: str) -> Dict[str, Any]:
    """Validates Python syntax statically using the Abstract Syntax Tree (AST)."""
    try:
        ast.parse(code)
        return {"valid": True, "error": None, "line": None}
    except SyntaxError as e:
        return {
            "valid": False,
            "error": str(e),
            "line": e.lineno
        }

def count_code_metrics(code: str) -> Dict[str, int]:
    """Calculates basic lines of code metrics for review panels."""
    lines = code.splitlines()
    total_lines = len(lines)
    blank_lines = sum(1 for line in lines if not line.strip())
    comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
    return {
        "total_lines": total_lines,
        "blank_lines": blank_lines,
        "comment_lines": comment_lines,
        "source_lines": total_lines - blank_lines - comment_lines
    }