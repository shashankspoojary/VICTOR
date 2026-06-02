import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Read individual string settings with sensible defaults
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "VICTOR")
VICTOR_USER_TITLE = os.getenv("VICTOR_USER_TITLE", "Sir")
VICTOR_OWNER_NAME = os.getenv("VICTOR_OWNER_NAME", "Shashank")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
GROQ_VLM_MODEL = os.getenv("GROQ_VLM__MODEL") or os.getenv("GROQ_VLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
TTS_VOICE = os.getenv("TTS_VOICE", "en-GB-RyanNeural")
TTS_RATE = os.getenv("TTS_RATE", "+22%")
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "127.0.0.1")

# Dynamically inspect all keys in os.environ using case-insensitive substring matching
GROQ_API_KEYS = []
GROQ_VLM_API_KEYS = []
TAVILY_API_KEYS = []

for key, value in os.environ.items():
    key_upper = key.upper()
    val_clean = value.strip().strip("'\"")
    
    if not val_clean:
        continue

    # Match keys containing 'GROQ_VLM_API_KEY'
    if 'GROQ_VLM_API_KEY' in key_upper:
        GROQ_VLM_API_KEYS.append(val_clean)
    # Match keys containing 'GROQ_API_KEY' (without 'VLM')
    elif 'GROQ_API_KEY' in key_upper and 'VLM' not in key_upper:
        GROQ_API_KEYS.append(val_clean)
    # Match keys containing 'TAVILY_API_KEY'
    elif 'TAVILY_API_KEY' in key_upper:
        TAVILY_API_KEYS.append(val_clean)

GROQ_API_KEYS.sort()
GROQ_VLM_API_KEYS.sort()
TAVILY_API_KEYS.sort()

if __name__ == "__main__":
    print(f"[CONFIG INIT] Loaded {len(GROQ_API_KEYS)} Groq keys, {len(GROQ_VLM_API_KEYS)} VLM keys, and {len(TAVILY_API_KEYS)} Tavily keys safely.")
