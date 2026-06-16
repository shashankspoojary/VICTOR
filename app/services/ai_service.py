import config
from app.utils.key_rotation import groq_rotator
from app.utils.retry import with_retry_and_rotation
from groq import AsyncGroq
from rich.console import Console

console = Console()

class AIService:
    @with_retry_and_rotation(rotator=groq_rotator, max_retries=3, base_delay=1.0)
    async def stream_chat_completion(self, messages: list, temperature: float = 0.7):
        api_key = groq_rotator.get_key()
        if not api_key:
            raise ValueError("No Groq API key available.")
            
        async with AsyncGroq(api_key=api_key) as client:
            stream = await client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            
            buffer = ""
            inside_thinking_block = False
            
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    buffer += content
                    
                    while buffer:
                        if not inside_thinking_block:
                            start_idx = buffer.find("<think>")
                            if start_idx != -1:
                                if start_idx > 0:
                                    yield buffer[:start_idx]
                                buffer = buffer[start_idx + len("<think>"):]
                                inside_thinking_block = True
                            else:
                                partial_match = False
                                for i in range(len("<think>") - 1, 0, -1):
                                    if buffer.endswith("<think>"[:i]):
                                        if len(buffer) > i:
                                            yield buffer[:-i]
                                        buffer = buffer[-i:]
                                        partial_match = True
                                        break
                                
                                if partial_match:
                                    break
                                else:
                                    yield buffer
                                    buffer = ""
                        else:
                            end_idx = buffer.find("</think>")
                            if end_idx != -1:
                                buffer = buffer[end_idx + len("</think>"):]
                                inside_thinking_block = False
                            else:
                                partial_match = False
                                for i in range(len("</think>") - 1, 0, -1):
                                    if buffer.endswith("</think>"[:i]):
                                        buffer = buffer[-i:]
                                        partial_match = True
                                        break
                                
                                if partial_match:
                                    break
                                else:
                                    buffer = ""

            if not inside_thinking_block and buffer:
                yield buffer

    @with_retry_and_rotation(rotator=groq_rotator, max_retries=3, base_delay=1.0)
    async def get_chat_completion(self, messages: list, model: str = None, response_format: dict = None, temperature: float = 0.1):
        api_key = groq_rotator.get_key()
        if not api_key:
            raise ValueError("No Groq API key available.")
            
        async with AsyncGroq(api_key=api_key) as client:
            model = model or config.GROQ_MODEL
            
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format
                
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

ai_service = AIService()
