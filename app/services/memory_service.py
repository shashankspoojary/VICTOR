import os
import json
from pathlib import Path
from app.utils.time_info import get_temporal_string

class MemoryService:
    def __init__(self):
        self.learning_data_dir = Path("database/learning_data")
        self.chats_data_dir = Path("database/chats_data")
        
        self.learning_data_dir.mkdir(parents=True, exist_ok=True)
        self.chats_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.learning_files = [
            "userdata.txt",
            "victor_personality.txt",
            "system_context.txt",
            "custom_notes.txt"
        ]

    def load_learning_data(self) -> dict:
        """
        Reads the text contents of the learning files.
        Returns a dictionary mapping the filename to its clean text content.
        Handles missing files gracefully.
        """
        data = {}
        for filename in self.learning_files:
            filepath = self.learning_data_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data[filename] = f.read().strip()
                except Exception:
                    data[filename] = ""
            else:
                data[filename] = ""
        return data

    def get_chat_history(self, session_id: str) -> list:
        """
        Retrieves the chat history for a given session.
        """
        filepath = self.chats_data_dir / f"{session_id}.json"
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def add_message(self, session_id: str, role: str, content: str):
        """
        Helper method to keep track of user and assistant messages for a session.
        """
        history = self.get_chat_history(session_id)
        history.append({"role": role, "content": content})
        filepath = self.chats_data_dir / f"{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

    def build_context(self, session_id: str, current_query: str) -> dict:
        """
        Master context assembler method.
        Gathers temporal info, reads learning data, fetches chat history,
        and combines these into a structured system prompt dictionary.
        """
        temporal_info = get_temporal_string()
        learning_data = self.load_learning_data()
        chat_history = self.get_chat_history(session_id)
        
        # Combine learning data into a system prompt
        system_prompt_parts = []
        system_prompt_parts.append(f"[{temporal_info}]")
        
        if learning_data.get("userdata.txt"):
            system_prompt_parts.append(f"--- User Data ---\n{learning_data['userdata.txt']}")
        if learning_data.get("victor_personality.txt"):
            system_prompt_parts.append(f"--- Personality ---\n{learning_data['victor_personality.txt']}")
        if learning_data.get("system_context.txt"):
            system_prompt_parts.append(f"--- System Context ---\n{learning_data['system_context.txt']}")
        if learning_data.get("custom_notes.txt"):
            system_prompt_parts.append(f"--- Custom Notes ---\n{learning_data['custom_notes.txt']}")
            
        system_prompt = "\n\n".join(system_prompt_parts)
        
        return {
            "system_prompt": system_prompt,
            "chat_history": chat_history,
            "current_query": current_query
        }
