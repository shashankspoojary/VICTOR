# app/services/desktop_service.py
import json
from datetime import datetime
from config import MULTIMODAL_DATA_DIR
from app.services.mouse_service import MouseService
from app.services.keyboard_service import KeyboardService
from app.services.system_monitor_service import SystemMonitorService
from app.services.environment_service import EnvironmentService
from app.utils.desktop_utils import open_application

class DesktopService:
    """Primary orchestration layer for Phase 4 desktop environment interactions."""
    
    def __init__(self):
        self.mouse_service = MouseService()
        self.keyboard_service = KeyboardService()
        self.system_monitor = SystemMonitorService()
        self.environment_service = EnvironmentService()
        
        self.actions_file = MULTIMODAL_DATA_DIR / "desktop_actions.json"
        self._ensure_actions_file()

    def _ensure_actions_file(self):
        if not self.actions_file.exists():
            with open(self.actions_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _log_action(self, action_type: str, details: str):
        try:
            with open(self.actions_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            history.append({
                "timestamp": datetime.now().isoformat(),
                "action": action_type,
                "details": details
            })
            if len(history) > 100:
                history = history[-100:]
            with open(self.actions_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except Exception:
            pass

    def launch_application(self, app_name: str, args: str = None) -> str:
        """Triggers local application launch using native OS shells."""
        self._log_action("launch_application", app_name)
        if not app_name:
            return "Application launch blocked: Target identifier missing."
        return open_application(app_name)

    def get_system_status(self, target: str = None, args: str = None) -> str:
        """Retrieves active CPU, RAM, Disk, and Process telemetry."""
        self._log_action("get_system_status", "Requested system resource telemetry")
        return self.system_monitor.get_system_status()

    def check_environment(self, target: str = None, args: str = None) -> str:
        """Surveys local tools and configurations available on the PATH."""
        self._log_action("check_environment", "Requested environment telemetry")
        return self.environment_service.detect_installed_tools()

    def mouse_action(self, action: str, params: str) -> str:
        """Interprets and executes targeted cursor manipulations."""
        self._log_action("mouse_action", f"{action} - {params}")
        try:
            action = action.lower()
            if action == "move":
                coords = [int(c.strip()) for c in params.split(",")]
                if len(coords) == 2:
                    return self.mouse_service.move_to(coords[0], coords[1])
                return "Syntax Error: Mouse move requires 'x,y' format."
            elif action == "click":
                return self.mouse_service.click()
            elif action == "position":
                pos = self.mouse_service.get_position()
                return f"Active Coordinates -> X:{pos['x']}, Y:{pos['y']}"
            return f"Unknown mouse instruction: {action}."
        except Exception as e:
            return f"Mouse action crashed: {str(e)}"

    def keyboard_action(self, action: str, params: str) -> str:
        """Interprets and executes keystrokes or text generation buffers."""
        self._log_action("keyboard_action", f"{action} - {params}")
        try:
            action = action.lower()
            if action == "type":
                return self.keyboard_service.type_text(params)
            elif action == "press":
                return self.keyboard_service.press_key(params)
            elif action == "hotkey":
                keys = [k.strip() for k in params.split(",")]
                return self.keyboard_service.hotkey(keys)
            return f"Unknown keyboard instruction: {action}."
        except Exception as e:
            return f"Keyboard action crashed: {str(e)}"