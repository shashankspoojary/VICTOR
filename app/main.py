from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.services.brain_service import BrainService

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
        query=payload.message
    )
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
