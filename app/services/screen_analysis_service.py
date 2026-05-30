# app/services/screen_analysis_service.py
import json
from datetime import datetime
from config import MULTIMODAL_DATA_DIR

class ScreenAnalysisService:
    """Transforms raw VLM output into structured historical understanding and handles persistence."""
    
    def __init__(self):
        self.history_file = MULTIMODAL_DATA_DIR / "screen_analysis.json"
        self._ensure_history()

    def _ensure_history(self):
        if not self.history_file.exists():
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def parse_vlm_output(self, vlm_text: str, context: str) -> dict:
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "summary": vlm_text,
            "has_error": "error" in vlm_text.lower() or "traceback" in vlm_text.lower()
        }
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            history.append(analysis)
            
            if len(history) > 50:
                history = history[-50:]
                
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4)
        except Exception:
            pass
            
        return analysis