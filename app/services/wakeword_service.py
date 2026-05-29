# app/services/wakeword_service.py
import asyncio
from app.services.voice_input_service import VoiceInputService

class WakewordService:
    def __init__(self):
        self.voice_input = VoiceInputService()
        self.wake_words = ["victor"]
        self.is_listening = False

    async def start_listening(self, callback) -> None:
        """
        Background loop waiting for the wake word.
        When detected, fires the callback to activate the main pipeline.
        """
        self.is_listening = True
        print(f"[WAKEWORD] System active. Listening for: {self.wake_words}")
        
        while self.is_listening:
            try:
                text = await self.voice_input.listen(timeout=2, phrase_time_limit=3)
                if text:
                    text_lower = text.lower()
                    if any(word in text_lower for word in self.wake_words):
                        print(f"[WAKEWORD] Wake phrase detected in: '{text}'")
                        await callback()
            except Exception:
                await asyncio.sleep(0.5)

    def stop_listening(self):
        self.is_listening = False