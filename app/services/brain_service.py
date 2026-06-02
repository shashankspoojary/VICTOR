import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time
import re
import logging
from typing import List, Tuple, Dict, Any

import config
from app.utils.key_rotation import groq_rotator

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

_PRIMARY_BRAIN_PROMPT = """You are the primary cognitive routing layer for VICTOR.
Your job is to analyze the user's input and recent chat history, then output EXACTLY ONE of the following classification strings:
- "camera": If the user explicitly asks to analyze what is currently visible on camera/screen, or asks questions about their environment.
- "task": If the user is giving a direct command to open an app, play media, control the system, generate an image, write content, or search the web (Google/YouTube).
- "mixed": If the user's input contains BOTH a conversational question AND a task command.
- "realtime": If the user is asking about current events, live news, real-time weather, or something that strictly requires live internet search to answer accurately.
- "general": For casual conversation, greetings, factual questions not requiring live search, or any other input.

Rules:
1. Output ONLY the single classification string in all lowercase. No punctuation, no extra words.
2. Consider contextual intelligence: if the user says "what about the other one" but history shows they were searching for something, it might be a followup search.
3. Handle corrections: if the user says "No, I meant to open X instead of Y", classify as "task".
4. Disambiguation: If unsure between general and realtime, default to general unless live data is strictly needed.
5. DO NOT output any <think> tags. Output the single word immediately.
"""

_TASK_BRAIN_PROMPT = """You are the secondary task parsing layer for VICTOR.
Parse the user's task request into one or more structured task lines.
Each line must be formatted as exactly: `task_type clean_query`
Available task types:
- open: To open a specific software or website (e.g. `open youtube`).
- open_webcam: To turn on or open the webcam/camera.
- close_webcam: To turn off or close the webcam/camera.
- play: To play a specific song, video, or media (e.g. `play lo-fi hip hop on youtube`).
- generate_image: To create, draw, or generate an image (e.g. `generate_image a futuristic city`).
- content: To write a specific document, code, or creative text (e.g. `content write a python script`).
- google_search: To search the web using Google (e.g. `google_search latest ai news`).
- youtube_search: To search YouTube specifically (e.g. `youtube_search best coding tutorials`).

Rules:
1. Strip all conversational filler ("please", "can you", "jarvis", "victor").
2. Only output the `task_type clean_query` lines.
3. If there are multiple tasks in the input, put each on a new line.
4. No other text, no explanations.
"""

class BrainService:
    def __init__(self):
        self.history = []
        
    def classify_primary(self, user_message: str, chat_history: list = None) -> str:
        if chat_history is None:
            chat_history = []
            
        history_context = chat_history[-6:]
        
        messages = [SystemMessage(content=_PRIMARY_BRAIN_PROMPT)]
        
        if history_context:
            history_text = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in history_context])
            human_content = f"Chat History:\n{history_text}\n\nUser Input: {user_message}"
        else:
            human_content = f"User Input: {user_message}"
            
        messages.append(HumanMessage(content=human_content))
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                llm = ChatGroq(
                    model=config.GROQ_MODEL,
                    temperature=0.0,
                    max_tokens=10,
                    api_key=groq_rotator.get_key()
                )
                response = llm.invoke(messages)
                raw_text = response.content.strip().lower()
                
                # Clean up punctuation and non-alpha characters
                cleaned = re.sub(r'[^a-z]', '', raw_text)
                
                valid_routes = ["general", "realtime", "camera", "task", "mixed"]
                for route in valid_routes:
                    if route in cleaned:
                        return route
                        
                return "general"  # fallback
            except Exception as e:
                logger.warning(f"Primary classification failed on attempt {attempt+1}: {e}")
                groq_rotator.rotate()
                time.sleep(1)
                
        return "general"  # Ultimate fallback
        
    def classify_task(self, user_message: str, chat_history: list = None) -> List[Tuple[str, str]]:
        user_lower = user_message.lower()
        
        # Fast-track rule-based regex checks
        if re.search(r'\\b(open|start|turn on) (webcam|camera)\\b', user_lower):
            return [("open_webcam", "")]
        if re.search(r'\\b(close|stop|turn off) (webcam|camera)\\b', user_lower):
            return [("close_webcam", "")]
            
        messages = [
            SystemMessage(content=_TASK_BRAIN_PROMPT),
            HumanMessage(content=user_message)
        ]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                llm = ChatGroq(
                    model=config.GROQ_MODEL,
                    temperature=0.0,
                    api_key=groq_rotator.get_key()
                )
                response = llm.invoke(messages)
                
                tasks = []
                lines = re.split(r'[,;]|\n+', response.content.strip())
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(maxsplit=1)
                    task_type = parts[0].lower()
                    clean_query = parts[1] if len(parts) > 1 else ""
                    
                    # Remove trailing punctuation or extra quotes if LLM added them
                    clean_query = re.sub(r'^["\']|["\']$', '', clean_query).strip()
                    
                    if task_type in ["open", "open_webcam", "close_webcam", "play", "generate_image", "content", "google_search", "youtube_search"]:
                        tasks.append((task_type, clean_query))
                
                if tasks:
                    return tasks
                
            except Exception as e:
                logger.warning(f"Task classification failed on attempt {attempt+1}: {e}")
                groq_rotator.rotate()
                time.sleep(1)
                
        return []
        
    def classify(self, user_message: str, chat_history: list = None) -> dict:
        route = self.classify_primary(user_message, chat_history)
        
        tasks = []
        if route in ["task", "mixed"]:
            tasks = self.classify_task(user_message, chat_history)
            
        return {
            "route": route,
            "tasks": tasks
        }

if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    
    # Overwrite the default Qwen model for evaluation since qwen requires <think> tags which break max_tokens=10
    import config
    config.GROQ_MODEL = "llama-3.1-8b-instant"

    logging.basicConfig(level=logging.INFO)
    brain = BrainService()
    
    test_inputs = [
        "Open YouTube and play lo-fi music",
        "Who won the latest football game?",
        "Hello Jarvis"
    ]
    
    print("=== Brain Service Evaluation ===")
    for inp in test_inputs:
        print(f"\n[Input] {inp}")
        result = brain.classify(inp)
        print(f"[Route] {result['route']}")
        if result['tasks']:
            print(f"[Tasks] {result['tasks']}")
