# app/utils/screen_utils.py
import mss
import mss.tools
import uuid
from pathlib import Path
from config import SCREENSHOTS_DIR

def capture_primary_screen() -> Path:
    """Captures the primary system monitor and saves the volatile snapshot to disk."""
    try:
        with mss.mss() as sct:
            # Index 1 corresponds to the primary display across OS platforms
            monitor = sct.monitors[1] 
            screenshot_path = SCREENSHOTS_DIR / f"screen_{uuid.uuid4().hex}.jpg"
            
            sct_img = sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, level=6, output=str(screenshot_path))
            
            return screenshot_path
    except Exception as e:
        print(f"[Screen Utils] Capture failure: {e}")
        return None