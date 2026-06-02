import threading
import logging
from typing import List

import config

logger = logging.getLogger(__name__)

class KeyRotator:
    def __init__(self, keys: List[str], label: str):
        self.keys = keys
        self.label = label
        self.index = 0
        self.lock = threading.Lock()

    def get_key(self) -> str:
        with self.lock:
            if not self.keys:
                return ""
            return self.keys[self.index]

    def rotate(self) -> None:
        with self.lock:
            if not self.keys:
                return
            old_index = self.index
            self.index = (self.index + 1) % len(self.keys)
            logger.info(f"[{self.label}] Rotated key from index {old_index} to {self.index}.")

# Instantiate and expose three global singleton engine instances
groq_rotator = KeyRotator(config.GROQ_API_KEYS, "Groq-LLM")
vlm_rotator = KeyRotator(config.GROQ_VLM_API_KEYS, "Groq-VLM")
tavily_rotator = KeyRotator(config.TAVILY_API_KEYS, "Tavily-Search")
