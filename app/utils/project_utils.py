# app/utils/project_utils.py
from pathlib import Path
import re
def generate_tree_directory(path: Path, prefix: str = "") -> str:
    """Recursively constructs a visual tree string of directories and source files."""
    if not path.exists():
        return "[Error: Specified path does not exist]"
    
    output = []
    # Sort files and directories to ensure deterministic tree layout
    entries = sorted(list(path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    entries_count = len(entries)
    
    for index, entry in enumerate(entries):
        is_last = (index == entries_count - 1)
        connector = "└── " if is_last else "├── "
        
        # Skip standard venv and cache tracks to keep visualization concise
        if entry.name in (".git", "__pycache__", "venv", ".env", ".DS_Store"):
            continue
            
        output.append(f"{prefix}{connector}{entry.name}")
        
        if entry.is_dir():
            next_prefix = prefix + ("    " if is_last else "│   ")
            subtree = generate_tree_directory(entry, next_prefix)
            if subtree:
                output.append(subtree)
                
    return "\n".join(output)

def validate_project_identifier(name: str) -> bool:
    """Ensures intended project names are safe for systemic directory generation."""
    if not name or len(name) > 64:
        return False
    return re.match(r"^[a-zA-Z0-9_\-]+$", name) is not None