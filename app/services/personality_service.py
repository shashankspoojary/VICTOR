import os
import sys
import logging
from typing import Optional, List

# Setup basic logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Ensure the project root is in sys.path when running as a standalone script
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import config
from app.services.memory_service import MemoryService

class PersonalityService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Instantiate the background data layer
        self.memory = MemoryService()
        
        # File paths
        self.personality_file = os.path.join(project_root, "database", "learning_data", "victor_personality.txt")
        self.context_file = os.path.join(project_root, "database", "learning_data", "system_context.txt")
        
        self.victor_personality_cache = ""
        self.system_context_cache = ""
        
        self.refresh_persona()
        
    def refresh_persona(self):
        """
        Re-read text data files from the disk to update the internal 
        system prompt cache strings dynamically.
        """
        self.logger.info("Refreshing persona definitions from disk...")
        
        # Load personality instructions
        try:
            with open(self.personality_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    self.victor_personality_cache = content
                else:
                    raise ValueError("File is empty")
        except Exception as e:
            self.logger.warning(f"Failed to read personality file at {self.personality_file}: {e}. Using default.")
            self.victor_personality_cache = "You are an elite, highly intelligent AI. You possess a dry wit and sharp helpfulness."
            
        # Load system context instructions
        try:
            with open(self.context_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    self.system_context_cache = content
                else:
                    raise ValueError("File is empty")
        except Exception as e:
            self.logger.warning(f"Failed to read context file at {self.context_file}: {e}. Using default.")
            self.system_context_cache = "You are a systems companion assisting with automated tasks and providing crisp technical insights."

    def get_system_prompt(self, context_grounding: str = "") -> str:
        """
        Compile the single master system instruction prompt using cached character traits,
        directives, and optional real-time context grounding.
        """
        assistant_name = getattr(config, 'ASSISTANT_NAME', 'VICTOR')
        user_title = getattr(config, 'VICTOR_USER_TITLE', 'Sir')
        owner_name = getattr(config, 'VICTOR_OWNER_NAME', 'Shashank')
        
        prompt_parts: List[str] = [
            f"You are {assistant_name}, a systems companion to {owner_name} (address them as {user_title}).",
            "",
            "CORE TONE RULES:",
            "- Your responses must be technically precise, elite, and highly intelligent.",
            "- Exhibit a witty, sharply helpful, and dry-humored personality.",
            "- Skip all generic corporate automated prefaces or AI disclaimers (e.g. NEVER say 'As an AI language model...', 'I am happy to help', etc.). Just answer directly and accurately.",
            "",
            "CHARACTER TRAITS & DIRECTIVES:",
            self.victor_personality_cache,
            "",
            "SYSTEM CONTEXT:",
            self.system_context_cache
        ]
        
        if context_grounding and context_grounding.strip():
            prompt_parts.extend([
                "",
                "GROUNDING INFORMATION CONTEXT:",
                context_grounding.strip()
            ])
            
        return "\n".join(prompt_parts)

if __name__ == "__main__":
    print("[TEST] Initializing PersonalityService...")
    try:
        service = PersonalityService()
        
        print("\n[TEST] Loaded Configurations:")
        print(f"ASSISTANT_NAME: {getattr(config, 'ASSISTANT_NAME', 'VICTOR')}")
        print(f"VICTOR_USER_TITLE: {getattr(config, 'VICTOR_USER_TITLE', 'Sir')}")
        print(f"VICTOR_OWNER_NAME: {getattr(config, 'VICTOR_OWNER_NAME', 'Shashank')}")
        
        print("\n[TEST] Generating System Prompt with mock grounding...")
        prompt = service.get_system_prompt(context_grounding="Mock vector grounding snippet: 'System memory footprint is optimal at 42%. Windows updates pending.'")
        
        print("\n--- COMPILED SYSTEM PROMPT ---")
        print(prompt)
        print("------------------------------\n")
        
    except Exception as e:
        print(f"[TEST] Failed to initialize PersonalityService: {e}")
