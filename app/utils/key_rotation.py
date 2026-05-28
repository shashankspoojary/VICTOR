from config import GROQ_API_KEYS, TAVILY_API_KEYS

class KeyRotationManager:
    """Generic manager to rotate through available API keys to handle limits/failures."""
    def __init__(self, keys: list[str], service_name: str):
        self.keys = keys
        self.current_index = 0
        self.service_name = service_name

    def get_current_key(self) -> str:
        if not self.keys:
            raise ValueError(f"No API keys configured for {self.service_name}.")
        return self.keys[self.current_index]

    def rotate_key(self) -> str:
        if not self.keys:
            raise ValueError(f"No API keys configured for {self.service_name}.")
        self.current_index = (self.current_index + 1) % len(self.keys)
        print(f"\n[KEY ROTATION] {self.service_name} API limit hit. Switched to key index {self.current_index}")
        return self.keys[self.current_index]

# Instantiate independent managers for our services
groq_key_manager = KeyRotationManager(GROQ_API_KEYS, "Groq")
tavily_key_manager = KeyRotationManager(TAVILY_API_KEYS, "Tavily")