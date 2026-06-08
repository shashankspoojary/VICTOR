import base64
import config
from groq import AsyncGroq
from app.utils.key_rotation import groq_vlm_rotator
from app.utils.retry import with_retry_and_rotation

class VisionService:
    @with_retry_and_rotation(rotator=groq_vlm_rotator, max_retries=3, base_delay=1.0)
    async def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        api_key = groq_vlm_rotator.get_key()
        if not api_key:
            raise ValueError("No Groq VLM API key available.")
            
        client = AsyncGroq(api_key=api_key)
        
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{base64_image}"
        
        messages = [
            {
                "role": "system",
                "content": "You are a vision-capable AI assistant. You are looking at a webcam snapshot or an uploaded image from the user. Analyze the image and answer the user's query directly by describing what you see. Do not claim you are unable to see images or perceive the physical world, since the image is provided directly to you."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                ],
            }
        ]
        
        response = await client.chat.completions.create(
            model=config.GROQ_VLM_MODEL,
            messages=messages,
            temperature=0.1
        )
        
        return response.choices[0].message.content

vision_service = VisionService()
