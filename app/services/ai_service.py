import logging
import re
import os
import base64
from typing import Optional
import edge_tts
import httpx

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import config
from app.utils.key_rotation import llm_key_manager, vlm_key_manager
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

class AIService:
    """The Cloud AI Service Layer for VICTOR."""

    @async_retry(retries=3, initial_delay=1.0, backoff_factor=2.0, key_manager=llm_key_manager)
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        current_key = llm_key_manager.get_current_key()
        if not current_key:
            raise ValueError("No active LLM API key available.")
            
        logger.info(f"Generating text with model {config.GROQ_MODEL} (key rotation active)")
        
        chat = ChatGroq(api_key=current_key, model_name=config.GROQ_MODEL)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
            
        messages.append(HumanMessage(content=prompt))
        
        response = await chat.ainvoke(messages)
        raw_content = response.content
        cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
        return cleaned_content
        
    @async_retry(retries=3, initial_delay=1.0, backoff_factor=2.0, key_manager=vlm_key_manager)
    async def generate_vision(self, prompt: str, base64_image: str) -> str:
        current_key = vlm_key_manager.get_current_key()
        if not current_key:
            raise ValueError("No active VLM API key available.")
            
        logger.info(f"Generating vision with model {config.GROQ_VLM_MODEL} (key rotation active)")
        
        chat = ChatGroq(api_key=current_key, model_name=config.GROQ_VLM_MODEL)
        
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
        
        messages = [HumanMessage(content=content)]
        response = await chat.ainvoke(messages)
        raw_content = response.content
        cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
        return cleaned_content

    async def generate_speech(self, text: str, session_id: str) -> str:
        clean_text = re.sub(r'[*#_~`]', '', text)
        communicate = edge_tts.Communicate(clean_text, voice=config.TTS_VOICE, rate=config.TTS_RATE)
        
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
                
        base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        return f"data:audio/mp3;base64,{base64_audio}"

    @async_retry(retries=3, initial_delay=1.0, backoff_factor=2.0, key_manager=llm_key_manager)
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        current_key = llm_key_manager.get_current_key()
        if not current_key:
            raise ValueError("No active LLM API key available.")
            
        logger.info(f"Transcribing audio with model whisper-large-v3 (key rotation active)")
        
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {current_key}"
        }
        
        files = {
            "file": (filename, audio_bytes, "audio/wav")
        }
        data = {
            "model": "whisper-large-v3"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            result = response.json()
            return result.get("text", "").strip()
