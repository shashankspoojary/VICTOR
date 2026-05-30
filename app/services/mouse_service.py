# app/services/mouse_service.py
import pyautogui

class MouseService:
    """Provides abstracted cursor movement and clicking capabilities."""
    
    def __init__(self):
        # Enforce fail-safes: moving the mouse to a corner manually aborts operations
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    def get_position(self) -> dict:
        x, y = pyautogui.position()
        return {"x": x, "y": y}

    def move_to(self, x: int, y: int, duration: float = 0.5) -> str:
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return f"Cursor successfully routed to coordinates X:{x}, Y:{y}."
        except Exception as e:
            return f"Mouse routing failure: {str(e)}"

    def click(self, x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
        try:
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, button=button, clicks=clicks)
                return f"Executed {clicks} '{button}' click(s) at X:{x}, Y:{y}."
            else:
                pyautogui.click(button=button, clicks=clicks)
                return f"Executed {clicks} '{button}' click(s) at current cursor position."
        except Exception as e:
            return f"Mouse actuation failure: {str(e)}"