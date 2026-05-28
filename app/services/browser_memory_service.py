# app/services/browser_memory_service.py
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from config import DATABASE_DIR

class BrowserMemoryService:
    """Manages transactional logging and historical telemetry persistence for browser actions."""
    
    def __init__(self):
        self.browser_data_dir = DATABASE_DIR / "browser_data"
        self.browser_data_dir.mkdir(parents=True, exist_ok=True)
        self.history_log = self.browser_data_dir / "browser_history.json"
        self._ensure_persistence_structures()

    def _ensure_persistence_structures(self):
        """Ensures storage data targets exist on disk."""
        if not self.history_log.exists():
            with open(self.history_log, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def log_navigation_event(self, url: str, title: str, execution_status: str):
        """Appends a new navigation track log to the browser history file."""
        try:
            with open(self.history_log, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            history.append({
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "title": title,
                "status": execution_status
            })
            
            with open(self.history_log, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            print(f"[BrowserMemoryService] Tracking write exception encountered: {e}")

    def fetch_recent_history(self, limitation_bound: int = 10) -> List[Dict[str, Any]]:
        """Retrieves history tracking entries from storage data files."""
        try:
            if not self.history_log.exists():
                return []
            with open(self.history_log, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data[-limitation_bound:]
        except Exception:
            return []