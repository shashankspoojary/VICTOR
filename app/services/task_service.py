# app/services/task_service.py
import json
import uuid
from datetime import datetime
from config import TASK_DATA_DIR

class TaskService:
    def __init__(self):
        self.history_file = TASK_DATA_DIR / "task_history.json"
        self._ensure_history_file()

    def _ensure_history_file(self):
        if not self.history_file.exists():
            self._save_history([])

    def _load_history(self) -> list:
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def _save_history(self, history: list):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4)

    def create_task(self, action: str, target: str, content: str = None) -> str:
        task_id = str(uuid.uuid4())
        task_record = {
            "id": task_id,
            "action": action,
            "target": target,
            "content": content,
            "status": "pending",
            "timestamp": datetime.now().isoformat()
        }
        history = self._load_history()
        history.append(task_record)
        self._save_history(history)
        return task_id

    def complete_task(self, task_id: str, result: str):
        self._update_status(task_id, "completed", result)

    def fail_task(self, task_id: str, error: str):
        self._update_status(task_id, "failed", error)

    def _update_status(self, task_id: str, status: str, meta: str):
        history = self._load_history()
        for t in history:
            if t["id"] == task_id:
                t["status"] = status
                t["result"] = meta
                break
        self._save_history(history)