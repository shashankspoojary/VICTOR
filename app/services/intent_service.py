# app/services/intent_service.py
from app.services.groq_service import GroqService

class IntentService:
    def __init__(self, groq_service: GroqService):
        self.groq_service = groq_service

    async def detect(self, message: str, use_search: bool) -> str:
        """Classifies user intention, ensuring browser actions map to the COMMAND pipeline."""
        # Retain V1 manual search checkbox toggle compatibility
        if use_search:
            return "SEARCH"

        msg_clean = message.strip().lower()

        # Hardcoded safeguard for basic greetings to minimize API latency
        if msg_clean in ["hi", "hii", "hello", "hey", "hola", "greetings", "sup", "yo"]:
            return "CHAT"

        # V4 Keyword Safeguard: Intercept browser automation intents immediately
        browser_keywords = [
            "search the web", "browser_search", "browser_navigate", 
            "web_extract", "web_analyze", "open website", "navigate to", 
            "extract page", "analyze webpage", "go to website"
        ]
        if any(keyword in msg_clean for keyword in browser_keywords):
            return "COMMAND"

        prompt = (
            "You are an expert intent classifier for a task-oriented AI assistant named VICTOR.\n"
            "Your job is to determine if the user is giving an instruction to execute a local system task or a web browser automation workflow.\n\n"
            "CRITICAL RULES:\n"
            "1. If the message is a greeting, small talk, general question, or conversational statement "
            "(like 'how are you', 'tell me a joke', 'who are you'), you MUST respond with 'CHAT'.\n"
            "2. Respond with 'COMMAND' if there is an explicit request to interact with the local PC filesystem, "
            "run terminal commands, or execute browser automation actions (e.g., searching the web, navigating to websites, scraping web content).\n\n"
            "Respond strictly with ONE WORD: 'COMMAND' or 'CHAT'. No punctuation, no explanation.\n\n"
            f"User Message: {message}"
        )
        
        try:
            classification = await self.groq_service.get_classification(prompt)
            if "COMMAND" in classification:
                return "COMMAND"
            return "CHAT"
        except Exception:
            return "CHAT"