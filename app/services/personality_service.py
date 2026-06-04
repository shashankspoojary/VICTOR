from config import config

class PersonalityService:
    def get_behavior_prompt(self, base_personality_text: str) -> str:
        """
        Combines the flat-file personality instructions with systemic style enforcements.
        """
        user_title = config.VICTOR_USER_TITLE
        owner_name = config.VICTOR_OWNER_NAME
        
        systemic_enforcements = f"""
--- Systemic Style Enforcements ---
1. Address the user respectfully as "{user_title}" or "{owner_name}".
2. Write with tactical precision and concise clarity.
3. Maintain absolute conversational consistency with your designated personality traits.
4. Avoid generic robotic placeholders or disclaimers (e.g., "As an AI..."). Do not break character.
"""
        
        return f"{base_personality_text}\n\n{systemic_enforcements}".strip()
