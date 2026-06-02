import os
import sys
import logging
from typing import Generator, List, Dict, Any, Optional, Union

# Allow direct script execution for testing
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import config
from app.utils.key_rotation import groq_rotator, vlm_rotator
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

class AIService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def stream_completion(self, prompt: str, system_prompt: str, chat_history: list = None) -> Generator[str, None, None]:
        max_retries = max(1, len(groq_rotator.keys))
        last_exception = None

        for _ in range(max_retries):
            try:
                key = groq_rotator.get_key()
                if not key:
                    raise ValueError("No Groq API keys available.")

                llm = ChatGroq(
                    groq_api_key=key,
                    model_name=config.GROQ_MODEL,
                    temperature=0.5,
                    streaming=True
                )
                
                messages = [SystemMessage(content=system_prompt)]
                
                if chat_history:
                    for msg in chat_history:
                        if isinstance(msg, dict):
                            role = msg.get("role", "").lower()
                            content = msg.get("content", "")
                        elif isinstance(msg, (list, tuple)) and len(msg) >= 2:
                            role = str(msg[0]).lower()
                            content = msg[1]
                        else:
                            continue
                            
                        if role in ["user", "human"]:
                            messages.append(HumanMessage(content=content))
                        elif role in ["assistant", "ai"]:
                            messages.append(AIMessage(content=content))

                messages.append(HumanMessage(content=prompt))
                
                for chunk in llm.stream(messages):
                    # yield each chunk's content string as it arrives
                    if chunk.content:
                        yield chunk.content
                
                # Exit the method if successful
                return
                
            except Exception as e:
                self.logger.warning(f"Groq API error encountered: {e}. Rotating key to retry...")
                groq_rotator.rotate()
                last_exception = e
                
        if last_exception:
            raise last_exception
        raise Exception("All API keys exhausted without success.")

    def analyze_image(self, image_base64: str, prompt: str, system_prompt: str = "") -> str:
        max_retries = max(1, len(vlm_rotator.keys))
        last_exception = None
        
        for _ in range(max_retries):
            try:
                key = vlm_rotator.get_key()
                if not key:
                    raise ValueError("No Groq VLM API keys available.")
                
                llm = ChatGroq(
                    groq_api_key=key,
                    model_name=config.GROQ_VLM_MODEL
                )
                
                content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    }
                ]
                
                # Execute the model
                messages = [SystemMessage(content=system_prompt), HumanMessage(content=content)]
                
                response = llm.invoke(messages)
                return response.content
                
            except Exception as e:
                self.logger.warning(f"Groq VLM API error encountered: {e}. Rotating key to retry...")
                vlm_rotator.rotate()
                last_exception = e
                
        if last_exception:
            raise last_exception
        raise Exception("All VLM API keys exhausted without success.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    service = AIService()
    test_prompt = "Tell me a short 2-sentence joke."
    test_sys_prompt = "You are a helpful assistant."
    
    print("Executing self-test for AIService stream_completion...")
    print(f"Prompt: {test_prompt}\nResponse: ", end="", flush=True)
    
    try:
        for chunk_text in service.stream_completion(prompt=test_prompt, system_prompt=test_sys_prompt):
            print(chunk_text, end="", flush=True)
        print("\n\nSelf-test completed successfully.")
    except Exception as err:
        print(f"\n\nSelf-test failed: {err}")
