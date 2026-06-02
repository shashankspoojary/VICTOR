import sys
import os
import logging

# Ensure project root is in the path to allow direct imports when run as __main__
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
from app.utils.key_rotation import groq_rotator, vlm_rotator
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

class AIService:
    def stream_completion(self, prompt: str, system_prompt: str, chat_history: list = None):
        """
        Stream completion responses robustly using key rotation.
        """
        if chat_history is None:
            chat_history = []
            
        max_retries = len(groq_rotator.keys)
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                key = groq_rotator.get_key()
                llm = ChatGroq(
                    model=config.GROQ_MODEL,
                    temperature=0.7,
                    api_key=key
                )
                
                messages = [SystemMessage(content=system_prompt)]
                
                for msg in chat_history:
                    # Parse standard dict chat histories or append as-is
                    if isinstance(msg, dict):
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "user":
                            messages.append(HumanMessage(content=content))
                        elif role in ("assistant", "model"):
                            messages.append(AIMessage(content=content))
                    else:
                        messages.append(msg)
                        
                messages.append(HumanMessage(content=prompt))
                
                for chunk in llm.stream(messages):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    elif isinstance(chunk, str):
                        yield chunk
                    else:
                        yield str(chunk)
                        
                return  # Successful completion, exit function
            except Exception as e:
                last_exception = e
                logger.warning(f"Error during stream_completion (attempt {attempt + 1}/{max_retries}): {e}")
                groq_rotator.rotate()
                
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("stream_completion failed, no keys configured.")

    def analyze_image(self, image_base64: str, prompt: str, system_prompt: str = "") -> str:
        """
        Analyze an image robustly using key rotation.
        """
        max_retries = len(vlm_rotator.keys)
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                key = vlm_rotator.get_key()
                llm = ChatGroq(
                    model=config.GROQ_VLM_MODEL,
                    api_key=key
                )
                
                content = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
                
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=content)
                ])
                
                if hasattr(response, "content"):
                    return response.content
                return str(response)
            except Exception as e:
                last_exception = e
                logger.warning(f"Error during analyze_image (attempt {attempt + 1}/{max_retries}): {e}")
                vlm_rotator.rotate()
                
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("analyze_image failed, no keys configured.")

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    logging.basicConfig(level=logging.INFO)
    
    print("Initializing AIService...")
    service = AIService()
    
    print("\nTesting stream_completion...")
    try:
        stream = service.stream_completion(
            prompt="Write a very short 1 sentence greeting.",
            system_prompt="You are a helpful AI.",
            chat_history=[]
        )
        for text_chunk in stream:
            print(text_chunk, end="", flush=True)
        print("\n\n[SUCCESS] Stream test complete.")
    except Exception as e:
        print(f"\n[ERROR] Stream test failed: {e}")
