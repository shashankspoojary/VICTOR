# app/services/keyboard_service.py
import pyautogui

class KeyboardService:
    """Provides abstracted typing and shortcut hotkey injection capabilities."""
    
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    def type_text(self, text: str, interval: float = 0.02) -> str:
        try:
            pyautogui.write(text, interval=interval)
            return f"Successfully typed payload."
        except Exception as e:
            return f"Keyboard injection failure: {str(e)}"

    def press_key(self, key: str) -> str:
        try:
            pyautogui.press(key)
            return f"Actuated single keystroke: '{key}'."
        except Exception as e:
            return f"Keystroke failure: {str(e)}"

    def hotkey(self, keys: list) -> str:
        try:
            pyautogui.hotkey(*keys)
            return f"Executed macro hotkey sequence: {' + '.join(keys)}."
        except Exception as e:
            return f"Hotkey execution failure: {str(e)}"