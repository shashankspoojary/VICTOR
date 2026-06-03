import json
import asyncio
import logging
import uuid
import sys
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Setup sys.path to ensure modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import services
from app.services.brain_service import BrainService
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService
from app.services.task_executor import TaskExecutor
from app.services.vision_service import VisionService
from app.services.realtime_service import RealtimeService
from app.services.personality_service import PersonalityService

from app.models import ChatRequest

logger = logging.getLogger(__name__)

# Initialize FastAPI App
app = FastAPI(title="VICTOR API Server")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate global instances of all imported services
brain_service = BrainService()
ai_service = AIService()
memory_service = MemoryService()
task_executor = TaskExecutor()
vision_service = VisionService()
realtime_service = RealtimeService()
personality_service = PersonalityService()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    return {"status": "completed"}


async def event_stream(req: ChatRequest):
    # Yield initial activity event mapping to frontend SSE specs
    yield f'data: {json.dumps({"activity": {"event": "query_detected", "message": "Thinking..."}})}\n\n'
    
    # Brain classification
    classification = brain_service.classify(req.message)
    route = classification.get("route", "general")
    
    # Yield the chosen route
    yield f'data: {json.dumps({"activity": {"event": "decision", "route": route}})}\n\n'
    
    context_grounding = ""
    
    # Route execution block
    if route == "camera" and req.imgbase64:
        context_grounding = vision_service.analyze_frame(req.imgbase64, req.message)
        
    elif route in ["task", "mixed"]:
        # Execute each parsed task and yield an 'actions' event
        for task in classification.get("tasks", []):
            task_type, clean_query = task
            action_dict = task_executor.execute_task(task_type, clean_query)
            yield f'data: {json.dumps({"actions": action_dict})}\n\n'
            
    elif route == "realtime":
        context_grounding = realtime_service.get_search_context(req.message)
        
    elif route == "general":
        context_grounding = memory_service.get_relevant_context(req.message)
        
    # Generate Response
    system_prompt = personality_service.get_system_prompt(context_grounding)
    
    # Yield streaming started
    yield f'data: {json.dumps({"activity": {"event": "streaming_started"}})}\n\n'
    
    # Loop over chunks returned by 'AIService.stream_completion()'
    for chunk in ai_service.stream_completion(req.message, system_prompt):
        yield f'data: {json.dumps({"chunk": chunk})}\n\n'
        
    # Finally, yield done
    yield f'data: {json.dumps({"done": True})}\n\n'


@app.post("/chat/jarvis/stream")
@app.post("/chat/victor/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(event_stream(req), media_type="text/event-stream")


if __name__ == "__main__":
    from app.banner import print_banner
    print_banner()
    print("[TEST] The main.py module is loaded successfully and all services are instantiated.")
    print("[TEST] You can run the server via: uvicorn app.main:app --host 127.0.0.1 --port 8000")
