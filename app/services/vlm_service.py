# app/services/vlm_service.py
import httpx
import asyncio
from config import VLM_MODEL, GROQ_VLM_API_KEYS

class VLMKeyManager:
    """Isolated key rotation manager specifically for VLM operations to protect standard chat capabilities."""
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.current_index = 0

    def get_current_key(self) -> str:
        if not self.keys:
            raise ValueError("No VLM API keys configured in environment.")
        return self.keys[self.current_index]

    def rotate_key(self) -> str:
        if not self.keys:
            raise ValueError("No VLM API keys configured in environment.")
        self.current_index = (self.current_index + 1) % len(self.keys)
        print(f"\n[VLM KEY ROTATION] VLM API limit hit. Switched to VLM key index {self.current_index}")
        return self.keys[self.current_index]

vlm_key_manager = VLMKeyManager(GROQ_VLM_API_KEYS)

class VLMService:
    """Vision model communication layer handling asynchronous payload execution."""
    
    def __init__(self):
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def analyze_image(self, base64_image: str, prompt: str) -> str:
        try:
            current_key = vlm_key_manager.get_current_key()
        except ValueError as e:
            return f"Error: {str(e)}"

        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": VLM_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }

        async with httpx.AsyncClient() as client:
            for attempt in range(3):
                try:
                    response = await client.post(self.base_url, headers=headers, json=payload, timeout=45.0)
                    if response.status_code in (429, 401, 403):
                        headers["Authorization"] = f"Bearer {vlm_key_manager.rotate_key()}"
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                except Exception as e:
                    if attempt == 2:
                        return f"VLM Analysis System Fault: {str(e)}"
                    await asyncio.sleep(1)
                    
        return "VLM Analysis Failed: Maximum structural retries exceeded."