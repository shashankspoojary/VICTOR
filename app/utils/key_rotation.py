import threading
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class KeyManager:
    """A thread-safe manager for API key rotation."""
    
    def __init__(self, name: str, keys: List[str]):
        self.name = name
        # Filter out empty or None values
        self.keys = [key for key in keys if key and isinstance(key, str)]
        self.current_index = 0
        self.lock = threading.Lock()
        
        if not self.keys:
            logger.warning(f"[{self.name}] No valid keys provided during initialization.")
        else:
            logger.info(f"[{self.name}] Initialized with {len(self.keys)} key(s).")
            
    def get_current_key(self) -> Optional[str]:
        """Returns the currently active API key, or None if no valid keys exist."""
        with self.lock:
            if not self.keys:
                return None
            return self.keys[self.current_index]
            
    def rotate_key(self) -> Optional[str]:
        """Rotates to the next available key in a round-robin cycle and returns it."""
        with self.lock:
            if not self.keys:
                return None
            
            old_index = self.current_index
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            # Don't log the actual key, just the rotation event
            logger.info(f"[{self.name}] Rotated key from index {old_index} to {self.current_index}")
            return self.keys[self.current_index]

# Initialize global key managers based on config
try:
    from config import config
except ImportError:
    logger.warning("Could not import config. Using empty key managers.")
    class DummyConfig:
        GROQ_API_KEY1 = ""
        GROQ_API_KEY2 = ""
        GROQ_API_KEY3 = ""
        GROQ_VLM_API_KEY_1 = ""
        GROQ_VLM_API_KEY_2 = ""
        GROQ_VLM_API_KEY_3 = ""
        TAVILY_API_KEY = ""
        TAVILY_API_KEY_2 = ""
        TAVILY_API_KEY_3 = ""
    config = DummyConfig()

llm_key_manager = KeyManager(
    name="LLM_Key_Manager",
    keys=[config.GROQ_API_KEY1, config.GROQ_API_KEY2, config.GROQ_API_KEY3]
)

vlm_key_manager = KeyManager(
    name="VLM_Key_Manager",
    keys=[config.GROQ_VLM_API_KEY_1, config.GROQ_VLM_API_KEY_2, config.GROQ_VLM_API_KEY_3]
)

tavily_key_manager = KeyManager(
    name="Tavily_Key_Manager",
    keys=[config.TAVILY_API_KEY, config.TAVILY_API_KEY_2, config.TAVILY_API_KEY_3]
)
