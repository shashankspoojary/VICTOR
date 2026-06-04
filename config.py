import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "127.0.0.1")
    
    # API Keys
    GROQ_API_KEY1 = os.getenv("GROQ_API_KEY1", "")
    GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2", "")
    GROQ_API_KEY3 = os.getenv("GROQ_API_KEY3", "")
    
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    TAVILY_API_KEY_2 = os.getenv("TAVILY_API_KEY_2", "")
    TAVILY_API_KEY_3 = os.getenv("TAVILY_API_KEY_3", "")
    
    GROQ_VLM_API_KEY_1 = os.getenv("GROQ_VLM_API_KEY_1", "")
    GROQ_VLM_API_KEY_2 = os.getenv("GROQ_VLM_API_KEY_2", "")
    GROQ_VLM_API_KEY_3 = os.getenv("GROQ_VLM_API_KEY_3", "")
    
    # Models
    GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
    GROQ_VLM_MODEL = os.getenv("GROQ_VLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    
    # TTS
    TTS_VOICE = os.getenv("TTS_VOICE", "en-GB-RyanNeural")
    TTS_RATE = os.getenv("TTS_RATE", "+22%")
    
    # Assistant Settings
    ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "VICTOR")
    VICTOR_USER_TITLE = os.getenv("VICTOR_USER_TITLE", "Sir")
    VICTOR_OWNER_NAME = os.getenv("VICTOR_OWNER_NAME", "Shashank")

config = Config()
