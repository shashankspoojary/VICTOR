# app/utils/audio_utils.py
import pygame
import time
import os

def init_audio_system():
    """Initializes the pygame mixer with optimal parameters for natural speech."""
    if not pygame.mixer.get_init():
        try:
            # edge-tts default output is 24kHz, 16-bit, Mono. Matching this prevents distortion.
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=512)
        except Exception:
            pygame.mixer.init()

def play_audio_file(filepath: str):
    """Plays a temporary audio file and forcefully unloads it to break Windows file locks."""
    try:
        init_audio_system()
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        
        # Block gracefully inside the executor thread until playback completes
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
            
        # CRITICAL FOR WINDOWS: Release the OS handle so the file can be instantly deleted
        pygame.mixer.music.unload()
    except Exception as e:
        print(f"[AUDIO UTILS] Playback Error: {e}")

def stop_audio():
    """Stops all active audio playback channel actions instantly."""
    if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()