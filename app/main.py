import asyncio
import json
import uvicorn
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sys
import os
import edge_tts
import base64
import re

# Ensure the root directory is on the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from app.services.brain_service import brain_service
from app.services.task_executor import task_executor
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from app.services.vision_service import vision_service
from app.models import TTSRequest

app = FastAPI(title="VICTOR Premium Web Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKGROUND_TASKS = {}

@app.get("/health")
async def health_endpoint():
    return {"status": "healthy"}

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    return BACKGROUND_TASKS.get(task_id, {"status": "not_found"})

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    tts: Optional[bool] = False
    imgbase64: Optional[str] = None
    files: Optional[List[dict]] = None

async def synthesize_speech_to_b64(text: str) -> Optional[str]:
    # Scrub text
    text = text.replace("*", "").replace("`", "")
    if not text.strip():
        return None
    try:
        communicate = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        if audio_data:
            return base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        print(f"TTS Error: {e}")
    return None

@app.post("/chat/victor/stream")
async def stream_endpoint(req: ChatRequest):
    prompt = req.message
    session_id = req.session_id or "default"
    use_tts = req.tts

    async def event_generator():
        try:
            yield "data: " + json.dumps({"activity": {"event": "request_received", "message": "Processing request..."}}) + "\n\n"

            if "TTCAMTOKENTT" in prompt:
                clean_prompt = prompt.replace("TTCAMTOKENTT", "").strip()
                upload_dir = config.DIRS["workspace_uploads"]
                files = [f for f in upload_dir.iterdir() if f.is_file()]
                if not files:
                    yield "data: " + json.dumps({'error': 'No image found for vision analysis.'}) + "\n\n"
                    yield "data: " + json.dumps({"done": True}) + "\n\n"
                    return
                
                most_recent_file = max(files, key=lambda f: f.stat().st_mtime)
                with open(most_recent_file, "rb") as f:
                    image_bytes = f.read()
                
                analysis = await vision_service.analyze_image(image_bytes, clean_prompt)
                
                yield "data: " + json.dumps({"chunk": analysis}) + "\n\n"
                
                if use_tts:
                    audio_b64 = await synthesize_speech_to_b64(analysis)
                    if audio_b64:
                        yield "data: " + json.dumps({"audio": audio_b64}) + "\n\n"

                yield "data: " + json.dumps({"done": True}) + "\n\n"
                return

            # 0. Retrieve conversational context
            context = await memory_service.get_context(session_id=session_id)

            # 1. Classify intent and get execution plan
            plan = await brain_service.classify_and_plan(prompt)
            
            # 2. Check if there are tasks to execute
            if plan.intent in ["task", "research", "vision"] and plan.execution_plan:
                yield "data: " + json.dumps({"activity": {"event": "task_plan", "message": "Executing task plan..."}}) + "\n\n"
                
                event_queue = asyncio.Queue()
                
                # Stream conversational acknowledgment token-by-token
                messages = [
                    {"role": "system", "content": f"You are {config.ASSISTANT_NAME}. Acknowledge the user's request and state you are executing the tasks. Keep it very short, tactical, and professional.\n\n{context}"},
                    {"role": "user", "content": prompt}
                ]
                
                ai_stream = ai_service.stream_chat_completion(messages)
                
                full_response_parts = []
                async def consume_ai_stream():
                    try:
                        sentence_buffer = ""
                        async for chunk in ai_stream:
                            full_response_parts.append(chunk)
                            await event_queue.put({"type": "chunk", "text": chunk})
                            
                            if use_tts:
                                sentence_buffer += chunk
                                match = re.search(r'(?<=[.!?])\s+', sentence_buffer)
                                if match:
                                    sentence = sentence_buffer[:match.end()].strip()
                                    sentence_buffer = sentence_buffer[match.end():]
                                    if sentence:
                                        await event_queue.put({"type": "tts_sentence", "text": sentence})

                        if use_tts and sentence_buffer.strip():
                            await event_queue.put({"type": "tts_sentence", "text": sentence_buffer.strip()})
                            
                    except Exception as e:
                        await event_queue.put({"type": "error", "text": str(e)})
                    finally:
                        await event_queue.put({"type": "_ai_done"})

                async def execute_tasks():
                    try:
                        await task_executor.execute_plan(plan.execution_plan, event_queue)
                    except Exception as e:
                        await event_queue.put({"type": "error", "text": str(e)})
                    finally:
                        await event_queue.put({"type": "_exec_done"})

                asyncio.create_task(consume_ai_stream())
                asyncio.create_task(execute_tasks())
                
                ai_done = False
                exec_done = False
                
                while not (ai_done and exec_done):
                    item = await event_queue.get()
                    if item["type"] == "_ai_done":
                        ai_done = True
                    elif item["type"] == "_exec_done":
                        exec_done = True
                    elif item["type"] == "chunk":
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        audio_b64 = await synthesize_speech_to_b64(item["text"])
                        if audio_b64:
                            yield "data: " + json.dumps({"audio": audio_b64}) + "\n\n"
                    elif item["type"] == "task_status":
                        yield "data: " + json.dumps({"activity": {"event": item.get('status'), "message": item.get('step')}}) + "\n\n"
                    elif item["type"] == "token":
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "error":
                        yield "data: " + json.dumps({"error": item["text"]}) + "\n\n"
                        
                full_response = "".join(full_response_parts)
                await memory_service.save_interaction(session_id, prompt, full_response)
            else:
                yield "data: " + json.dumps({"activity": {"event": "chat", "message": "Thinking..."}}) + "\n\n"
                
                messages = [
                    {"role": "system", "content": f"You are {config.ASSISTANT_NAME}, a highly capable AI tactical assistant.\n\n{context}"},
                    {"role": "user", "content": prompt}
                ]

                full_response_parts = []
                sentence_buffer = ""
                async for chunk in ai_service.stream_chat_completion(messages):
                    full_response_parts.append(chunk)
                    yield "data: " + json.dumps({"chunk": chunk}) + "\n\n"
                    
                    if use_tts:
                        sentence_buffer += chunk
                        match = re.search(r'(?<=[.!?])\s+', sentence_buffer)
                        if match:
                            sentence = sentence_buffer[:match.end()].strip()
                            sentence_buffer = sentence_buffer[match.end():]
                            if sentence:
                                audio_b64 = await synthesize_speech_to_b64(sentence)
                                if audio_b64:
                                    yield "data: " + json.dumps({"audio": audio_b64}) + "\n\n"
                                    
                if use_tts and sentence_buffer.strip():
                    audio_b64 = await synthesize_speech_to_b64(sentence_buffer.strip())
                    if audio_b64:
                        yield "data: " + json.dumps({"audio": audio_b64}) + "\n\n"

                full_response = "".join(full_response_parts)
                await memory_service.save_interaction(session_id, prompt, full_response)
                
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            
        finally:
            yield "data: " + json.dumps({"done": True}) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    upload_dir = config.DIRS["workspace_uploads"]
    file_path = upload_dir / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return {"filename": file.filename, "status": "saved"}

@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    async def audio_stream():
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(req.text, config.TTS_VOICE, rate=config.TTS_RATE)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        yield chunk["data"]
                break
            except Exception as e:
                print(f"TTS Retry {attempt+1} failed: {e}")
                await asyncio.sleep(0.5)
                
    return StreamingResponse(audio_stream(), media_type="audio/mpeg")

# Mount frontend at the root route to serve cleanly
app.mount("/", StaticFiles(directory=config.DIRS["frontend"], html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
