# app/services/debugging_service.py
import json
from pathlib import Path
from datetime import datetime
from config import DATABASE_DIR
from app.services.groq_service import GroqService

class DebuggingService:
    def __init__(self):
        self.groq_service = GroqService()
        self.history_log = DATABASE_DIR / "coding_data" / "debugging_history.json"
        self._ensure_persistence()

    def _ensure_persistence(self):
        if not self.history_log.exists():
            self.history_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_log, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _append_history(self, record: dict):
        try:
            with open(self.history_log, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data.append(record)
            with open(self.history_log, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    async def isolate_and_solve(self, traceback_text: str, source_code: str) -> dict:
        """Analyzes active failure reports and maps optimized correction strategies."""
        system_prompt = (
            "You are VICTOR's code debugging specialist interface.\n"
            "Analyze the provided traceback carefully and inspect the relevant source logic.\n"
            "Identify the root cause of the error and return a JSON object with two fields:\n"
            "- 'explanation': A concise, technical explanation of the issue.\n"
            "- 'remediation': The corrected version of the code snippet, complete and valid."
        )
        
        user_prompt = f"TRACEBACK LOG:\n{traceback_text}\n\nFAULTY SOURCE CODE:\n{source_code}"
        
        resolution = await self.groq_service.get_json_response(system_prompt, user_prompt)
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "traceback_summary": traceback_text[:200],
            "explanation": resolution.get("explanation", "Undefined structural breakdown"),
            "resolved": True
        }
        self._append_history(record)
        
        return resolution