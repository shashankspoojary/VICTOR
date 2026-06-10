import os
import json
import datetime
from pathlib import Path
import config

class MemoryService:
    def __init__(self):
        self.memory_dir = config.DIRS["database_memory"]
        self.learning_dir = config.DIRS["database_learning_data"]
        self.chats_dir = config.DIRS["database_chats_data"]
        self.memory_file = self.memory_dir / "memory.json"
        
        # Initialize memory file if it doesn't exist
        if not self.memory_file.exists():
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    async def get_context(self, session_id: str) -> str:
        now = datetime.datetime.now()
        context_parts = [
            "--- SYSTEM MEMORY & CONTEXT ---",
            f"\n[Current Time & Date]",
            f"The current local time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."
        ]
        
        # 1. Read personal settings and key facts from memory.json
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
                if memory_data:
                    context_parts.append("\n[Core Facts & Preferences]")
                    for k, v in memory_data.items():
                        if k == "user_owner_name":
                            context_parts.append(f"The user's name is {v}. You are his personal assistant, VICTOR.")
                        else:
                            context_parts.append(f"- {k}: {v}")
        except Exception as e:
            context_parts.append(f"\n[Error reading memory: {e}]")

        # 2. Read raw text files (.txt) inside learning_data/ dynamically
        try:
            txt_files = list(self.learning_dir.glob("*.txt"))
            if txt_files:
                context_parts.append("\n[Learning Data]")
                for txt_file in txt_files:
                    with open(txt_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        context_parts.append(f"--- {txt_file.name} ---\n{content}")
        except Exception as e:
            context_parts.append(f"\n[Error reading learning data: {e}]")

        # 3. Read last 10 conversational entries across all session files (newest files first)
        try:
            # Glob all .json files in the chats directory
            chat_files = list(self.chats_dir.glob("*.json"))
            # Sort by filesystem modification time (newest first)
            chat_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            recent_chats = []
            for chat_file in chat_files:
                if len(recent_chats) >= 10:
                    break
                try:
                    with open(chat_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            needed = 10 - len(recent_chats)
                            items = data[-needed:] if len(data) > needed else data
                            recent_chats = items + recent_chats
                        elif isinstance(data, dict):
                            recent_chats.insert(0, data)
                except Exception as e:
                    print(f"Error reading chat file {chat_file.name}: {e}")

            if recent_chats:
                context_parts.append("\n[Recent Conversation History]")
                for entry in recent_chats:
                    context_parts.append(f"User: {entry.get('user', '')}")
                    context_parts.append(f"Assistant: {entry.get('assistant', '')}")
        except Exception as e:
            context_parts.append(f"\n[Error reading chat history: {e}]")

        return "\n".join(context_parts)

    async def save_interaction(self, session_id: str, user_msg: str, assistant_response: str):
        try:
            # Ensure the chats directory exists
            self.chats_dir.mkdir(parents=True, exist_ok=True)
            
            chat_file = self.chats_dir / f"{session_id}.json"
            chat_data = []
            if chat_file.exists():
                with open(chat_file, "r", encoding="utf-8") as f:
                    try:
                        chat_data = json.load(f)
                        if not isinstance(chat_data, list):
                            chat_data = []
                    except json.JSONDecodeError:
                        pass
            
            chat_data.append({
                "user": user_msg,
                "assistant": assistant_response
            })

            with open(chat_file, "w", encoding="utf-8") as f:
                json.dump(chat_data, f, indent=2)
        except Exception as e:
            print(f"Error saving interaction: {e}")

    async def update_memory(self, fact_key: str, fact_value: str):
        try:
            memory_data = {}
            if self.memory_file.exists():
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    try:
                        memory_data = json.load(f)
                    except json.JSONDecodeError:
                        pass
                        
            memory_data[fact_key] = fact_value
            
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, indent=2)
        except Exception as e:
            print(f"Error updating memory: {e}")

    async def remove_memory(self, fact_key: str):
        try:
            if self.memory_file.exists():
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    try:
                        memory_data = json.load(f)
                    except json.JSONDecodeError:
                        memory_data = {}
                
                if fact_key in memory_data:
                    del memory_data[fact_key]
                    with open(self.memory_file, "w", encoding="utf-8") as f:
                        json.dump(memory_data, f, indent=2)
        except Exception as e:
            print(f"Error removing memory: {e}")

memory_service = MemoryService()
