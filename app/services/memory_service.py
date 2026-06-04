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
        self.knowledge_library_dir = Path("knowledge_library")
        self.knowledge_library_dir.mkdir(parents=True, exist_ok=True)

    def load_knowledge_library(self, category: str) -> str:
        """
        Recursively reads all .txt, .md, or code files inside knowledge_library/{category}.
        Concatenates their text strings into a structured reference block.
        """
        category_dir = self.knowledge_library_dir / category
        if not category_dir.exists() or not category_dir.is_dir():
            return ""

        allowed_extensions = {".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".sh", ".yml", ".yaml"}
        content_parts = []
        
        try:
            for filepath in category_dir.rglob("*"):
                if filepath.is_file() and filepath.suffix.lower() in allowed_extensions:
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            file_content = f.read().strip()
                            if file_content:
                                content_parts.append(f"--- Knowledge Library Reference [{filepath.name}] ---\n{file_content}\n---")
                    except Exception:
                        pass
        except Exception:
            pass
            
        return "\n\n".join(content_parts)

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

    def build_context(self, session_id: str, current_query: str, mode: str = None) -> dict:
        """
        Master context assembler method.
        Gathers temporal info, reads learning data, fetches chat history,
        and combines these into a structured system prompt dictionary.
        Also loads dynamic context from knowledge library if mode is KNOWLEDGE_MODE.
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
            
        if mode == 'KNOWLEDGE_MODE':
            category = "custom"
            query_lower = current_query.lower()
            if any(kw in query_lower for kw in ["code", "programming", "python", "javascript", "html", "css", "bug"]):
                category = "coding"
            elif "script" in query_lower:
                category = "scripts"
            elif "business" in query_lower:
                category = "business"
            
            knowledge_data = self.load_knowledge_library(category)
            if knowledge_data:
                system_prompt_parts.append(knowledge_data)

        system_prompt = "\n\n".join(system_prompt_parts)
        
        return {
            "system_prompt": system_prompt,
            "chat_history": chat_history,
            "current_query": current_query
        }
