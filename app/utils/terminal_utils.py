# app/utils/terminal_utils.py
import os
import shutil
import re

def is_executable_available(name: str) -> bool:
    """Verifies if a specific utility or runtime binary is discoverable in system PATH."""
    return shutil.which(name) is not None

def clean_terminal_sequences(text: str) -> str:
    """Removes ANSI escape codes and terminal color sequences from stdout stream output."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def build_safe_environment() -> dict:
    """Generates a clean environment dict preserving standard Python path adjustments."""
    env = os.environ.copy()
    # Prevent interactive prompts from blocking background executions
    env["PYTHONUNBUFFERED"] = "1"
    env["DEBIAN_FRONTEND"] = "noninteractive"
    return env