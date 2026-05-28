# app/main.py
import sys
import asyncio

# Prevent Uvicorn from downgrading the event loop on Windows inside the worker thread
if sys.platform == "win32":
    try:
        asyncio.WindowsSelectorEventLoopPolicy = asyncio.WindowsProactorEventLoopPolicy
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("[INFRASTRUCTURE] Worker Process: Uvicorn event loop downgrade blocked.")
    except Exception as e:
        print(f"[INFRASTRUCTURE ERROR] Failed to patch event loop policy: {e}")

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from app.models import ChatRequest
from app.services.brain_service import BrainService

app = FastAPI(title="VICTOR API v4")
brain_service = BrainService()

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Primary chat endpoint utilizing streaming response."""
    
    async def response_generator():
        # Pass the use_search flag to the Brain Service
        async for chunk in brain_service.process_chat(
            request.session_id, 
            request.message, 
            request.use_search
        ):
            yield chunk

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/health")
def health_check():
    return {"status": "VICTOR Backend Operational"}