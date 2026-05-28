# app/services/terminal_service.py
import subprocess
from pathlib import Path
from datetime import datetime
from app.utils.terminal_utils import clean_terminal_sequences, build_safe_environment
from app.services.workspace_service import WorkspaceService

class TerminalService:
    def __init__(self):
        self.workspace_manager = WorkspaceService()

    def run_development_command(self, command: str, working_dir: str = None, timeout: int = 15) -> dict:
        """Executes a development terminal process inside a designated context safehouse."""
        exec_cwd = working_dir if working_dir else str(self.workspace_manager.workspace_root)
        
        # Check command structure safety patterns
        dangerous_keywords = ["rm -rf /", "mkfs", "dd ", "> /dev/sda"]
        if any(kw in command.lower() for kw in dangerous_keywords):
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Security Exception: Blocked high-risk terminal pattern command.",
                "success": False
            }

        start_time = datetime.now()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=exec_cwd,
                text=True,
                capture_output=True,
                timeout=timeout,
                env=build_safe_environment()
            )
            
            stdout_clean = clean_terminal_sequences(result.stdout)
            stderr_clean = clean_terminal_sequences(result.stderr)
            success = (result.returncode == 0)
            
            self._log_execution(command, exec_cwd, stdout_clean, stderr_clean, result.returncode)
            
            return {
                "returncode": result.returncode,
                "stdout": stdout_clean,
                "stderr": stderr_clean,
                "success": success
            }
            
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution interrupted: Process timed out beyond {timeout} seconds.",
                "success": False
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Subprocess system error: {str(e)}",
                "success": False
            }

    def _log_execution(self, cmd: str, cwd: str, out: str, err: str, code: int):
        log_file = self.workspace_manager.logs_dir / "terminal_execution.log"
        timestamp = datetime.now().isoformat()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] CWD: {cwd} | CMD: {cmd} | CODE: {code}\n")
            if out: f.write(f"STDOUT:\n{out}\n")
            if err: f.write(f"STDERR:\n{err}\n")
            f.write("-" * 40 + "\n")