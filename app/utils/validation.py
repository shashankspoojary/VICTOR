# app/utils/validation.py
import os
from pathlib import Path

def is_safe_path(target_path: str) -> bool:
    """
    Global access enabled. 
    Resolves the path to ensure it is syntactically valid for the OS,
    but allows creation anywhere on the PC.
    """
    try:
        # We still resolve it to catch malformed path strings, 
        # but we removed the BASE_DIR restriction.
        requested_path = Path(target_path).resolve()
        return True
    except Exception:
        return False

def is_safe_command(command: str) -> bool:
    """Basic validation to prevent catastrophic terminal commands."""
    dangerous_keywords = ["rm -rf /*", "mkfs", "dd ", "> /dev/sda"]
    cmd_lower = command.lower()
    for word in dangerous_keywords:
        if word in cmd_lower:
            return False
    return True