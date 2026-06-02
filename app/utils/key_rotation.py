import os
import itertools
from typing import List

class KeyRotation:
    def __init__(self):
        self.keys = self._load_keys()
        self.key_cycle = itertools.cycle(self.keys) if self.keys else None

    def _load_keys(self) -> List[str]:
        keys = []
        index = 1
        while True:
            key = os.getenv(f"GROQ_API_KEY{index}")
            if key:
                keys.append(key)
                index += 1
            else:
                break
        return keys

    def get_next_key(self) -> str:
        if not self.key_cycle:
            raise ValueError("No GROQ_API_KEY found in environment variables.")
        return next(self.key_cycle)
