# app/services/coding_service.py
from app.services.groq_service import GroqService
from app.utils.code_utils import clean_python_code, validate_python_syntax

class CodingService:
    def __init__(self):
        self.groq_service = GroqService()

    async def generate_source_code(self, context_prompt: str, instructions: str) -> dict:
        """Asynchronously triggers the infrastructure core to compose contextual code components."""
        system_instructions = (
            "You are VICTOR's internal system programming architect engine.\n"
            "Your task is to write clean, modular, production-grade Python code adhering strictly to design guidelines.\n"
            "CRITICAL: Return only executable codebase items inside markdown standard code structures.\n"
            "Do not include conversational preamble, explanations, or meta commentary outside code wrappers."
        )
        
        user_payload = f"SYSTEM ARCHITECTURE CONTEXT:\n{context_prompt}\n\nDEVELOPMENT ASSIGNMENT:\n{instructions}"
        
        # Call low latency structure to capture payload accurately
        raw_response = await self.groq_service.get_json_response(
            system_prompt=system_instructions,
            user_prompt=user_payload
        )
        
        # Extract response from standard JSON structural wrapper safely
        extracted_code = raw_response.get("code", "") if isinstance(raw_response, dict) else ""
        if not extracted_code:
            # Fallback handling to streaming context mapping if response format variations happen
            extracted_code = clean_python_code(str(raw_response))
            
        validation = validate_python_syntax(extracted_code)
        
        return {
            "raw_code": extracted_code,
            "syntax_valid": validation["valid"],
            "syntax_error": validation["error"]
        }

    async def explain_code_segment(self, code: str) -> str:
        """Asynchronously details architectural decisions and interfaces found within code segments."""
        prompt = (
            f"Analyze and break down this source code structure into clear functional blocks:\n\n```python\n{code}\n```"
        )
        messages = [{"role": "user", "content": prompt}]
        explanation = ""
        async for chunk in self.groq_service.stream_chat(messages):
            explanation += chunk
        return explanation