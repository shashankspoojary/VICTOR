# app/services/speech_pipeline_service.py
import asyncio
from app.services.voice_input_service import VoiceInputService
from app.services.voice_output_service import VoiceOutputService
from app.services.brain_service import BrainService
from app.utils.voice_utils import sanitize_for_tts, is_sentence_end

class SpeechPipelineService:
    def __init__(self, brain_service: BrainService):
        self.input_service = VoiceInputService()
        self.output_service = VoiceOutputService()
        self.brain_service = brain_service

    async def execute_voice_interaction(self, session_id: str, use_search: bool = False):
        """
        Orchestrates a single complete voice interaction cycle:
        Listen -> Brain Stream -> Chunk to Sentences -> Synthesize TTS -> Play.
        """
        # 1. Listen for User Input
        user_text = await self.input_service.listen()
        
        if not user_text:
            return

        # Stop any ongoing speech if user interrupted
        self.output_service.stop()

        # 2. Process via BrainService with Voice Mode enabled
        print(f"[SPEECH PIPELINE] Routing to Brain: {user_text}")
        response_generator = self.brain_service.process_chat(
            session_id=session_id, 
            user_message=user_text, 
            use_search=use_search,
            is_voice=True  # Important: Informs brain to alter personality prompt
        )

        # 3. Buffer LLM tokens and stream sentences to TTS dynamically
        sentence_buffer = ""
        
        async for chunk in response_generator:
            if not chunk:
                continue
                
            sentence_buffer += chunk
            
            # If we hit punctuation, flush the buffer to TTS
            if is_sentence_end(sentence_buffer):
                clean_text = sanitize_for_tts(sentence_buffer)
                if clean_text:
                    await self.output_service.speak(clean_text)
                sentence_buffer = ""
                
        # Flush remaining text in buffer
        if sentence_buffer.strip():
            clean_text = sanitize_for_tts(sentence_buffer)
            if clean_text:
                await self.output_service.speak(clean_text)