# app/services/voice_input_service.py
import speech_recognition as sr
import asyncio
from typing import Optional

class VoiceInputService:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Calibrate energy triggers for home ambient noise levels
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        
        self.audio_queue = asyncio.Queue()
        self._stop_listening_fn = None
        self._is_running = False
        self._loop = None
        self.microphone = None

    def start_continuous_listening(self):
        """Spawns an efficient background thread that keeps the mic hardware open continuously."""
        if self._is_running:
            return # STATE GUARD: Already active, protect against redundant calls
            
        self._is_running = True
        self._loop = asyncio.get_running_loop()
        self.microphone = sr.Microphone()
        
        # Calibrate for ambient noise once before starting thread loop
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        def background_callback(recognizer, audio):
            try:
                # Direct streaming to Google Cloud Speech API
                text = recognizer.recognize_google(audio)
                if text and text.strip():
                    # Thread-safe insertion into the main async loop's queue
                    self._loop.call_soon_threadsafe(self.audio_queue.put_nowait, text)
            except sr.UnknownValueError:
                pass # Suppress noise spikes gracefully
            except sr.RequestError as e:
                print(f"[VOICE INPUT] Cloud API Connection Issue: {e}")

        # Bind native background audio daemon thread
        self._stop_listening_fn = self.recognizer.listen_in_background(
            self.microphone, 
            background_callback, 
            phrase_time_limit=12
        )
        print("[VOICE INPUT] Continuous background listening stream initialized.")

    def stop_continuous_listening(self):
        """Gracefully disconnects from the microphone hardware handle with strict state guards."""
        if not self._is_running:
            return # STATE GUARD: Microphone is already down, exit silently instead of spamming logs
            
        self._is_running = False
        if self._stop_listening_fn:
            self._stop_listening_fn(wait_for_stop=False)
            self._stop_listening_fn = None
        
        # Clear out any residual phrases left behind in queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        print("[VOICE INPUT] Microphone deactivated cleanly.")

    async def get_next_phrase(self) -> Optional[str]:
        """Polls the background audio queue. Uses a short timeout to keep interface responsive."""
        if not self._is_running:
            return None
        try:
            return await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None