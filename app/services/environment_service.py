# app/services/environment_service.py
import json
from datetime import datetime
from config import MULTIMODAL_DATA_DIR
from app.utils.os_utils import find_executable

class EnvironmentService:
    """Scans the local filesystem PATH to identify available developer runtimes and tools."""
    
    def __init__(self):
        self.state_file = MULTIMODAL_DATA_DIR / "environment_state.json"
        self.critical_tools = ["python", "node", "git", "docker", "npm", "pip", "java", "go", "rustc"]
        self._ensure_state()

    def _ensure_state(self):
        if not self.state_file.exists():
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def detect_installed_tools(self) -> str:
        installed = []
        missing = []
        
        for tool in self.critical_tools:
            if find_executable(tool):
                installed.append(tool)
            else:
                missing.append(tool)

        state = {
            "timestamp": datetime.now().isoformat(),
            "installed": installed,
            "missing": missing
        }

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)

        installed_str = ", ".join(installed) if installed else "None detected"
        missing_str = ", ".join(missing) if missing else "None"

        return (
            f"--- ENVIRONMENT AWARENESS ---\n"
            f"Available Runtimes & Tools: {installed_str}\n"
            f"Missing Configurations: {missing_str}\n"
            f"-----------------------------"
        )