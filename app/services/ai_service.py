import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from app.utils.key_rotation import KeyRotation

class AIService:
    def __init__(self):
        self.key_rotation = KeyRotation()
        self.model_name = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")

    def generate(self, prompt: str) -> str:
        api_key = self.key_rotation.get_next_key()
        
        chat = ChatGroq(
            api_key=api_key,
            model_name=self.model_name
        )
        
        messages = [HumanMessage(content=prompt)]
        response = chat.invoke(messages)
        
        return str(response.content)
