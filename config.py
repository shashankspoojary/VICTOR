import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory for the project (where config.py is located)
BASE_DIR = Path(__file__).resolve().parent

# Define system directories based on frozen architecture
DIRS = {
    "frontend": BASE_DIR / "frontend",
    "app": BASE_DIR / "app",
    "database_learning_data": BASE_DIR / "database" / "learning_data",
    "database_chats_data": BASE_DIR / "database" / "chats_data",
    "database_memory": BASE_DIR / "database" / "memory",
    "workspace_uploads": BASE_DIR / "workspace" / "uploads",
    "workspace_temp": BASE_DIR / "workspace" / "temp",
}

def ensure_directories():
    """Ensure all required system directories exist on import."""
    for path in DIRS.values():
        path.mkdir(parents=True, exist_ok=True)

# Ensure required directories exist
ensure_directories()

# --- Central Constants & Configuration ---

# Server
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# API Keys
GROQ_API_KEY1 = os.getenv("GROQ_API_KEY1")
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")
GROQ_API_KEY3 = os.getenv("GROQ_API_KEY3")

TAVILY_API_KEY_1 = os.getenv("TAVILY_API_KEY_1")
TAVILY_API_KEY_2 = os.getenv("TAVILY_API_KEY_2")
TAVILY_API_KEY_3 = os.getenv("TAVILY_API_KEY_3")

GROQ_VLM_API_KEY_1 = os.getenv("GROQ_VLM_API_KEY_1")
GROQ_VLM_API_KEY_2 = os.getenv("GROQ_VLM_API_KEY_2")
GROQ_VLM_API_KEY_3 = os.getenv("GROQ_VLM_API_KEY_3")

# Models
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
GROQ_VLM_MODEL = os.getenv("GROQ_VLM_MODEL", "llama-3.2-90b-vision-preview")

# Text-to-Speech Settings
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")
TTS_RATE = os.getenv("TTS_RATE", "+0%")

# Persona Settings
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "VICTOR")
VICTOR_USER_TITLE = os.getenv("VICTOR_USER_TITLE", "Sir")
VICTOR_OWNER_NAME = os.getenv("VICTOR_OWNER_NAME", "User")
