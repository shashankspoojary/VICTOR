import config
from rich.console import Console

console = Console()

class KeyRotator:
    def __init__(self, service_name: str, keys: list):
        self.service_name = service_name
        self.keys = [k for k in keys if k]
        self.current_index = 0
        
        if not self.keys:
            console.print(f"[bold red]Warning: No API keys configured for {service_name}[/bold red]")

    def get_key(self):
        if not self.keys:
            return None
        return self.keys[self.current_index]

    def rotate_key(self):
        if not self.keys:
            return None
        self.current_index = (self.current_index + 1) % len(self.keys)
        console.print(f"[bold yellow][{self.service_name} Key Rotator][/bold yellow] Rotated to key index {self.current_index}")
        return self.keys[self.current_index]

# Initialize rotators
groq_rotator = KeyRotator("Groq", [
    config.GROQ_API_KEY1, 
    config.GROQ_API_KEY2, 
    config.GROQ_API_KEY3
])

tavily_rotator = KeyRotator("Tavily", [
    config.TAVILY_API_KEY_1, 
    config.TAVILY_API_KEY_2, 
    config.TAVILY_API_KEY_3
])

groq_vlm_rotator = KeyRotator("Groq VLM", [
    config.GROQ_VLM_API_KEY_1, 
    config.GROQ_VLM_API_KEY_2, 
    config.GROQ_VLM_API_KEY_3
])
