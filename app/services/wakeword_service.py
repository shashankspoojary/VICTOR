# app/services/wakeword_service.py
from typing import Tuple

class WakewordService:
    def __init__(self):
        # Configurable lists for state transitions
        self.wake_words = ["victor", "wake up", "hey victor", "listen up"]
        self.sleep_words = ["end session", "see you later", "stop listening", "go to sleep", "goodbye", "pause session"]

    def analyze_phrase(self, text: str) -> Tuple[str, str]:
        """
        Analyzes streaming text for wake or sleep commands.
        Returns: 
            command_type: 'WAKE', 'SLEEP', or 'NONE'
            cleaned_text: The remaining text payload after stripping the trigger word.
        """
        text_lower = text.lower().strip()
        
        # 1. Check for termination/sleep commands
        for word in self.sleep_words:
            if word in text_lower:
                return 'SLEEP', ""

        # 2. Check for activation/wake commands
        for word in self.wake_words:
            if word in text_lower or text_lower.startswith(word):
                # Extract the actual command by stripping the wake word
                clean_payload = text_lower.replace(word, "", 1).strip()
                # Clean up residual punctuation from speech recognition (e.g., "Victor, do this" -> "do this")
                clean_payload = clean_payload.strip(",.!? ")
                return 'WAKE', clean_payload
        
        # No triggers detected
        return 'NONE', text