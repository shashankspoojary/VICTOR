import os
from fastapi import FastAPI
from dotenv import load_dotenv
from app.models import ChatRequest, ChatResponse
from app.services.ai_service import AIService

load_dotenv()

app = FastAPI(title=os.getenv("ASSISTANT_NAME", "VICTOR"))
ai_service = AIService()

@app.get("/health")
def health():
    return {
        "status": "online",
        "assistant": os.getenv("ASSISTANT_NAME", "VICTOR")
    }

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    response_text = ai_service.generate(request.message)
    return ChatResponse(response=response_text)
