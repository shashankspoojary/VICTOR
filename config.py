# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).parent.absolute()
DATABASE_DIR = BASE_DIR / "database"
WORKSPACE_DIR = BASE_DIR / "workspace"

# Sub-database Paths
LEARNING_DATA_DIR = DATABASE_DIR / "learning_data"
CHATS_DATA_DIR = DATABASE_DIR / "chats_data"
VECTOR_STORE_DIR = DATABASE_DIR / "vector_store"
TASK_DATA_DIR = DATABASE_DIR / "task_data"
WORKFLOW_TEMPLATES_DIR = DATABASE_DIR / "workflow_templates"

# V5: Multimodal & Voice Paths
MULTIMODAL_DATA_DIR = DATABASE_DIR / "multimodal_data"
VOICE_CACHE_DIR = WORKSPACE_DIR / "voice_cache"

# V5 Phase 3: Vision Paths
VISION_CACHE_DIR = WORKSPACE_DIR / "vision_cache"
SCREENSHOTS_DIR = WORKSPACE_DIR / "screenshots"

# Ensure directories exist
for path in [
    LEARNING_DATA_DIR, CHATS_DATA_DIR, VECTOR_STORE_DIR, 
    TASK_DATA_DIR, WORKFLOW_TEMPLATES_DIR, MULTIMODAL_DATA_DIR, VOICE_CACHE_DIR,
    VISION_CACHE_DIR, SCREENSHOTS_DIR
]:
    path.mkdir(parents=True, exist_ok=True)

# API Keys
GROQ_API_KEYS = [
    key for key in [
        os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3")
    ] if key
]

GROQ_VLM_API_KEYS = [
    key for key in [
        os.getenv("GROQ_VLM_API_KEY"),
        os.getenv("GROQ_VLM_API_KEY_2"),
        os.getenv("GROQ_VLM_API_KEY_3")
    ] if key
]

TAVILY_API_KEYS = [
    key for key in [
        os.getenv("TAVILY_API_KEY"),
        os.getenv("TAVILY_API_KEY_2"),
        os.getenv("TAVILY_API_KEY_3")
    ] if key
]

# Model Config
MAIN_MODEL = os.getenv("MAIN_MODEL", "qwen/qwen3-32b") 
ROUTING_MODEL = os.getenv("ROUTING_MODEL", "llama-3.1-8b-instant")
VLM_MODEL = os.getenv("VLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Memory Config
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "victor_memory.index"

# Voice Config
VOICE_TTS_MODEL = "en-GB-RyanNeural"