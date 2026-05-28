# app/utils/command_utils.py
import subprocess
from app.utils.validation import is_safe_command

def safe_run_command(command: str) -> str:
    if not is_safe_command(command):
        raise PermissionError("Blocked dangerous command.")
        
    try:
        # Use a timeout to prevent hanging commands
        result = subprocess.run(
            command, 
            shell=True, 
            text=True, 
            capture_output=True, 
            timeout=10
        )
        if result.returncode == 0:
            return f"Command succeeded:\n{result.stdout.strip()}"
        else:
            return f"Command failed:\n{result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Execution error: {str(e)}"