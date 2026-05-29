# app/services/voice_output_service.py
import os
import asyncio
import tempfile
import uuid
import edge_tts
from config import VOICE_TTS_MODEL
from app.utils.audio_utils import play_audio_file, stop_audio

class VoiceOutputService:
    def __init__(self):
        self.voice_model = VOICE_TTS_MODEL
        self._playback_queue = asyncio.Queue()
        self._is_playing = False
        
        # Continuous background consumer worker
        asyncio.create_task(self._playback_worker())

    async def speak(self, text: str):
        """Synthesizes text into a transient system file and queues it for playback."""
        if not text or not text.strip():
            return

        # Redirect target paths directly to the system's volatile Temp directory
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"victor_transient_{uuid.uuid4().hex}.mp3")
        
        try:
            communicate = edge_tts.Communicate(text, self.voice_model)
            await communicate.save(file_path)
            await self._playback_queue.put(file_path)
        except Exception as e:
            print(f"[VOICE OUTPUT] TTS Generation Failure: {e}")

    async def _playback_worker(self):
        """Sequentially consumes audio playback tracking requests and cleans up instantly."""
        while True:
            file_path = await self._playback_queue.get()
            self._is_playing = True
            
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, play_audio_file, file_path)
            finally:
                self._is_playing = False
                self._playback_queue.task_done()
                
                # Immediate eradication of the file from disk
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass # Handled gracefully if cleanup registers a delay

    def stop(self):
        """Stops ongoing speech outputs and purges any queued files remaining."""
        stop_audio()
        while not self._playback_queue.empty():
            try:
                file_path = self._playback_queue.get_nowait()
                self._playback_queue.task_done()
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                break