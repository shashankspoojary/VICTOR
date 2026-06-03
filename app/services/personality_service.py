import os
import sys
import logging
from typing import Optional, List

# Ensure the root directory is in sys.path so we can import 'config' and 'app' modules when run directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import config
from app.services.memory_service import MemoryService

class PersonalityService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.memory = MemoryService()

    def get_identity_prompt(self, dynamic_context: str = "") -> str:
        # Retrieve static user profile parameters safely from configuration values
        assistant_name = getattr(config, 'ASSISTANT_NAME', 'VICTOR')
        user_title = getattr(config, 'VICTOR_USER_TITLE', 'Sir')
        owner_name = getattr(config, 'VICTOR_OWNER_NAME', 'Shashank')

        # Compute paths for character configuration files
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        personality_path = os.path.join(base_dir, 'database', 'learning_data', 'victor_personality.txt')
        context_path = os.path.join(base_dir, 'database', 'learning_data', 'system_context.txt')

        # Read character configurations from disk or fallback to safe structural default definitions
        try:
            with open(personality_path, 'r', encoding='utf-8') as f:
                personality_text = f.read().strip()
        except Exception as e:
            self.logger.warning(f"Could not read {personality_path}: {e}")
            personality_text = "Tone guidelines: Highly intelligent, clean, technically elite, precise, and possessing a witty, dry, systems-companion humor. You must avoid long conversational filler or generic automated disclosures (e.g., 'As an AI language model...')."

        try:
            with open(context_path, 'r', encoding='utf-8') as f:
                system_context_text = f.read().strip()
        except Exception as e:
            self.logger.warning(f"Could not read {context_path}: {e}")
            system_context_text = "You are the central core processing engine operating locally on this machine."

        # Assemble comprehensive, explicit system prompt wrapper string
        prompt_parts: List[str] = [
            f"Your name is strictly {assistant_name}.",
            f"You are interacting with your owner {owner_name}, whom you address respectfully yet sharply as \"{user_title}\".",
            "",
            "--- BEHAVIORAL & TONE GUIDELINES ---",
            personality_text,
            "",
            "--- SYSTEM CONTEXT ---",
            system_context_text
        ]

        if dynamic_context:
            prompt_parts.extend([
                "",
                "GROUNDING INFORMATION:",
                dynamic_context
            ])

        return "\n".join(prompt_parts)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        service = PersonalityService()
        prompt = service.get_identity_prompt(dynamic_context="Test vector grounding data chunk")
        
        print("=== VICTOR SYSTEM PROMPT BLOCK ===")
        print(prompt)
        print("==================================")
    except Exception as e:
        print(f"Test failed: {e}")
