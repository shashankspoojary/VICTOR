import os
import base64
import config
from groq import AsyncGroq
from app.utils.key_rotation import groq_vlm_rotator
from app.utils.retry import with_retry_and_rotation
from app.services.face_service import face_service

class VisionService:
    @with_retry_and_rotation(rotator=groq_vlm_rotator, max_retries=3, base_delay=1.0)
    async def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        api_key = groq_vlm_rotator.get_key()
        if not api_key:
            raise ValueError("No Groq VLM API key available.")
            
        # Temporarily save image for face recognition
        temp_path = os.path.join(config.DIRS["workspace_uploads"], "temp_webcam.jpg")
        with open(temp_path, "wb") as f:
            f.write(image_bytes)
            
        face_info = face_service.identify_face(temp_path)
        face_context = ""
        if face_info:
            if face_info["status"] == "known":
                face_context = f"\n[Face Recognition System] IDENTIFIED: {face_info['name']} ({face_info['relationship']}). Greet them by name and mention the relationship."
            elif face_info["status"] == "unknown":
                face_context = "\n[Face Recognition System] UNKNOWN HUMAN DETECTED. In your response, after answering the query, YOU MUST ask: 'I see someone in the image. Would you like me to save their identity?'"
        
        client = AsyncGroq(api_key=api_key)
        
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{base64_image}"
        
        system_content = "You are a vision-capable AI assistant. You are looking at a webcam snapshot or an uploaded image from the user. Analyze the image and answer the user's query directly by describing what you see. Do not claim you are unable to see images or perceive the physical world, since the image is provided directly to you."
        if face_context:
            system_content += f"\n{face_context}"
            
        messages = [
            {
                "role": "system",
                "content": system_content
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
