import logging
import re
import os
from typing import Optional
import edge_tts

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
        
        output_dir = "workspace/temp"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/speech_{session_id}.mp3"
        
        await communicate.save(output_path)
        
        return f"/static_workspace/temp/speech_{session_id}.mp3"
