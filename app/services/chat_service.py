from typing import List, Dict
from app.services.session_service import SessionService

class ChatService:
    def __init__(self):
        self.session_service = SessionService()

    def get_history(self, session_id: str) -> List[Dict]:
        """Retrieves formatted chat history for AI context."""
        return self.session_service.load_session(session_id)

    def append_message(self, session_id: str, role: str, content: str):
        """Appends a single message to the session."""
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})
        
        # Keep history manageable (e.g., last 20 messages)
        if len(history) > 20:
            history = history[-20:]
            
        self.session_service.save_session(session_id, history)

    def prepare_messages_for_ai(self, session_id: str, system_prompt: str, new_user_message: str) -> List[Dict]:
        """Compiles history and new message into standard API format."""
        history = self.get_history(session_id)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": new_user_message})
        return messages