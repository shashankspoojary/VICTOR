# app/services/window_analysis_service.py
import pygetwindow as gw
from typing import Dict, Any

class WindowAnalysisService:
    """Detects active desktop window layouts to provide situational awareness to the VLM."""
    
    def get_active_window_info(self) -> Dict[str, Any]:
        try:
            active_window = gw.getActiveWindow()
            if active_window:
                return {
                    "title": active_window.title,
                    "is_maximized": active_window.isMaximized,
                    "width": active_window.width,
                    "height": active_window.height
                }
            return {"title": "Unknown OS Context", "status": "No active window detected"}
        except Exception as e:
            return {"title": "System Desktop", "error": str(e)}