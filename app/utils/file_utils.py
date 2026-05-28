# app/utils/file_utils.py
import os
from pathlib import Path
from app.utils.validation import is_safe_path

def safe_create_folder(target_path: str) -> str:
    if not is_safe_path(target_path):
        raise PermissionError("Path traversal detected or unauthorized directory access.")
    
    path = Path(target_path)
    if path.exists():
        return f"Directory '{target_path}' already exists."
        
    path.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {target_path}"

def safe_create_file(target_path: str, content: str) -> str:
    if not is_safe_path(target_path):
        raise PermissionError("Path traversal detected or unauthorized file access.")
        
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"Created file: {target_path}"