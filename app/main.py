from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.services.brain_service import BrainService
from app.services.memory_service import MemoryService
from app.services.ai_service import AIService
import os

app = FastAPI(title="VICTOR API")

# Configure robust CORSMiddleware permissions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, including local file schemes/localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject references to BrainService
brain_service = BrainService()

class ChatRequest(BaseModel):
    message: str
    session_id: str
    mode: str | None = None
    ttsEnabled: bool = False

class VisionRequest(BaseModel):
    message: str
    image: str
    session_id: str

@app.get("/api/status")
async def get_status():
    """
    Returns a clean confirmation payload showing VICTOR is online and operational.
    """
    return {
        "status": "online", 
        "message": "VICTOR is online and operational."
    }

@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest):
    """
    Accepts a chat payload and asynchronously passes it to BrainService.
    """
    response = await brain_service.execute_query(
        session_id=payload.session_id,
        query=payload.message,
        mode=payload.mode
    )
    
    if payload.ttsEnabled:
        ai_service = AIService()
        audio_url = await ai_service.generate_speech(response, payload.session_id)
        return {"response": response, "audio_url": audio_url}
        
    return {"response": response}

@app.post("/api/vision")
async def vision_endpoint(payload: VisionRequest):
    """
    Routes vision payload directly through the vision capability architecture.
    """
    # Prepend deterministic guard token so BrainService routes it to vision
    query_with_token = f"TTCAMTOKENTT {payload.message}"
    
    response = await brain_service.execute_query(
        session_id=payload.session_id,
        query=query_with_token,
        base64_image=payload.image
    )
    return {"response": response}

@app.post("/api/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    audio_content = await file.read()
    ai_service = AIService()
    text = await ai_service.transcribe_audio(audio_content, file.filename)
    return {"transcript": text}

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), session_id: str = Form(...)):
    raw_bytes = await file.read()
    memory_service = MemoryService()
    context_str = memory_service.extract_document_text(file.filename, raw_bytes)
    if context_str:
        memory_service.add_message(session_id, "system", context_str)
        return {"status": "success", "message": "Document added to context."}
    return {"status": "error", "message": "Failed to extract document context."}


# Ensure workspace directory exists before mounting
os.makedirs("workspace", exist_ok=True)

# Mount static frontend
app.mount("/static_workspace", StaticFiles(directory="workspace"), name="workspace")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
