# app/services/system_monitor_service.py
import json
from datetime import datetime
from config import MULTIMODAL_DATA_DIR
from app.utils.system_utils import get_cpu_usage, get_memory_usage, get_disk_usage, get_top_processes

class SystemMonitorService:
    """Harvests real-time hardware telemetry and running application processes."""
    
    def __init__(self):
        self.history_file = MULTIMODAL_DATA_DIR / "system_history.json"
        self._ensure_history()

    def _ensure_history(self):
        if not self.history_file.exists():
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _log_state(self, state: dict):
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                
            history.append({
                "timestamp": datetime.now().isoformat(),
                "state": state
            })
            if len(history) > 100:
                history = history[-100:]
                
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except Exception:
            pass

    def get_system_status(self) -> str:
        """Compiles a text-based readout of the machine's current operational state."""
        cpu = get_cpu_usage()
        mem = get_memory_usage()
        disk = get_disk_usage()
        procs = get_top_processes(7)

        self._log_state({
            "cpu_percent": cpu,
            "memory_percent": mem["percent"],
            "disk_percent": disk["percent"]
        })

        proc_lines = "\n".join([f" - {p['name']} (PID: {p['pid']} | CPU: {p.get('cpu_percent', 0.0)}% | RAM: {p.get('memory_percent', 0.0):.1f}%)" for p in procs if p])

        return (
            f"--- SYSTEM RESOURCE STATUS ---\n"
            f"CPU Load: {cpu}%\n"
            f"RAM Load: {mem['percent']}%\n"
            f"Primary Disk Load: {disk['percent']}%\n\n"
            f"Heaviest Active Processes:\n{proc_lines}\n"
            f"------------------------------"
        )