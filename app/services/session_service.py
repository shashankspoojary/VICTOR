import json
from pathlib import Path
from typing import List, Dict
from config import CHATS_DATA_DIR

class SessionService:
    @staticmethod
    def get_session_path(session_id: str) -> Path:
        return CHATS_DATA_DIR / f"{session_id}.json"

    def load_session(self, session_id: str) -> List[Dict]:
        path = self.get_session_path(session_id)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_session(self, session_id: str, history: List[Dict]):
        path = self.get_session_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)