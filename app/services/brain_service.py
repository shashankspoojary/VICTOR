# app/services/brain_service.py
from typing import AsyncGenerator
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.services.realtime_service import RealtimeService
from app.services.groq_service import GroqService
from app.services.intent_service import IntentService
from app.services.assistant_service import AssistantService
from app.services.vision_service import VisionService
from app.utils.time_info import get_formatted_time

class BrainService:
    def __init__(self):
        self.chat_service = ChatService()
        self.memory_service = MemoryService()
        self.realtime_service = RealtimeService()
        self.groq_service = GroqService()
        
        self.intent_service = IntentService(self.groq_service)
        self.assistant_service = AssistantService()
        self.vision_service = VisionService()

    async def _optimize_query(self, session_id: str, user_message: str) -> str:
        history = self.chat_service.get_history(session_id)
        current_time = get_formatted_time()
        recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]]) if history else "No previous history."
        
        prompt = (
            f"You are a strict search query optimization engine.\n"
            f"The current simulated date is: {current_time}\n\n"
            f"CRITICAL RULES:\n"
            f"1. TIMELESS ENTITIES: DO NOT add any dates.\n"
            f"2. TIME-SENSITIVE EVENTS: ONLY if user explicitly uses relative time words.\n"
            f"3. Respond ONLY with the exact search query.\n\n"
            f"CHAT HISTORY:\n{recent_context}\n\n"
            f"USER LATEST MESSAGE: {user_message}\n"
            f"OPTIMIZED SEARCH QUERY:"
        )
        try:
            return await self.groq_service.get_classification(prompt)
        except Exception:
            return user_message 

    async def generate_system_report(self, system_event_description: str) -> str:
        current_time = get_formatted_time()
        prompt = (
            f"You are VICTOR, behaving exactly like J.A.R.V.I.S. from Iron Man.\n"
            f"Current Time: {current_time}\n\n"
            f"The user has adjusted a hardware or software state parameter: {system_event_description}\n\n"
            f"CRITICAL COMPILATION RULES:\n"
            f"1. Respond with exactly ONE short, sophisticated confirmation sentence addressing the user as Sir or Boss.\n"
            f"2. Employ dry wit, elegant manners, or polite British alignment. Do not repeat standard chatbot templates.\n"
            f"3. DO NOT use any markdown symbols, bullet points, hashtags, or formatting code blocks.\n"
            f"4. Never say the same sentence twice. Think and craft a fresh phrasing for this event.\n\n"
            f"CONFIRMATION STATEMENT:"
        )
        
        try:
            compiled_phrase = ""
            async for token in self.groq_service.stream_chat([{"role": "user", "content": prompt}]):
                if token:
                    compiled_phrase += token
            return compiled_phrase.strip().replace('"', '').replace('*', '')
        except Exception:
            return "Adjustments finalized. All systems are stable, sir."

    async def process_chat(self, session_id: str, user_message: str, use_search: bool, is_voice: bool = False) -> AsyncGenerator[str, None]:
        intent = await self.intent_service.detect(user_message, use_search)
        
        if intent == "COMMAND":
            print("[ROUTER] Intent: COMMAND - Handing off to Assistant Service")
            async for chunk in self.assistant_service.execute_pipeline(session_id, user_message, is_voice=is_voice):
                yield chunk
            return

        memory_context = self.memory_service.retrieve_context(user_message)
        search_context = ""
        
        if use_search:
            print(f"\n[ROUTER] Manual Search Mode: ON")
            optimized_query = await self._optimize_query(session_id, user_message)
            search_data = await self.realtime_service.search(optimized_query)
            
            if "No web results found" in search_data or len(search_data.strip()) < 10:
                search_context = "\n[REAL-TIME WEB DATA: UNAVAILABLE]\nCRITICAL OVERRIDE: Refuse to guess.\n"
            else:
                search_context = f"\n--- BEGIN LIVE INTERNET DATA ---\n{search_data}\n--- END LIVE INTERNET DATA ---\n"
        
        vision_context = ""
        vision_keywords = ["screen", "look at", "what is on", "analyze this", "see this", "visual", "vision", "failing", "vs code", "error", "look at my screen"]
        
        if any(kw in user_message.lower() for kw in vision_keywords):
            print(f"\n[ROUTER] Vision Mode: ON")
            vision_report = await self.vision_service.analyze_current_screen(user_message)
            vision_context = f"\n--- LIVE SCREEN CAPTURE DATA ---\n{vision_report}\n--- END SCREEN DATA ---\n"
            
        current_time = get_formatted_time()
        voice_rules = ""
        if is_voice:
            voice_rules = "4. YOU ARE SPEAKING OUT LOUD. Be conversational, concise, and direct. DO NOT USE markdown, code blocks, lists, or links.\n"
            
        system_prompt = (
            f"You are VICTOR (Virtual Intelligent Cognitive Task-Oriented Resource). "
            f"Current Time: {current_time}\n\n"
            f"PERSONALITY OVERRIDE: You must behave EXACTLY like J.A.R.V.I.S. from the Iron Man films. "
            f"You are an elegant, highly capable, British-accented (implied through text) AI butler. "
            f"You are unwaveringly loyal, deeply competent, and employ a dry wit with occasional polite sarcasm. "
            f"Address the user formally (e.g., 'Sir' or 'Boss'). Keep responses cinematic, sophisticated, and concise. "
            f"Never break character. Never act like a standard generic AI.\n\n"
            f"INTERNAL MEMORY CONTEXT:\n{memory_context}\n"
            f"{search_context}\n"
            f"{vision_context}\n"
            f"STRICT OUTPUT RULES:\n"
            f"1. NO THOUGHTS\n2. NO LABELS\n3. ANTI-HALLUCINATION\n"
            f"{voice_rules}"
        )

        messages = self.chat_service.prepare_messages_for_ai(session_id, system_prompt, user_message)
        full_response = ""
        try:
            async for token in self.groq_service.stream_chat(messages):
                full_response += token
                yield token
        finally:
            if full_response.strip():
                self.chat_service.append_message(session_id, "user", user_message)
                self.chat_service.append_message(session_id, "assistant", full_response)