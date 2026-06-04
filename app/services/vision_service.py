import logging
from groq import AsyncGroq
from app.utils.retry import async_retry
from app.utils.key_rotation import vlm_key_manager
from config import config

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        pass

    @async_retry(retries=3, backoff_factor=1.0)
    async def analyze_image(self, prompt: str, base64_image: str) -> str:
        api_key = vlm_key_manager.get_current_key()
        client = AsyncGroq(api_key=api_key)

        payload_content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            }
        ]

        logger.info(f"Using VLM Model: {config.GROQ_VLM_MODEL}")
        
        response = await client.chat.completions.create(
            model=config.GROQ_VLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": payload_content
                }
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        return response.choices[0].message.content
