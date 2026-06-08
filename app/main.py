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

class ChatPayload(BaseModel):
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

async def _distill_answer(raw_text: str, query: str) -> str:
    messages = [
        {"role": "system", "content": "You are a concise data extractor. Read the provided search results and provide ONLY the specific, current numeric answer to the user's question. Do not include markdown, do not include reasoning, do not repeat the question. 1 sentence max."},
        {"role": "user", "content": f"User Question: {query}\nSearch Results: {raw_text}"}
    ]
    parts = []
    try:
        async for chunk in ai_service.stream_chat_completion(messages):
            parts.append(chunk)
    except Exception as e:
        print(f"Error distilling answer: {e}")
    return "".join(parts).strip()

@app.get("/api/stream")
async def get_stream_endpoint(prompt: str, session_id: Optional[str] = "default", tts: Optional[bool] = False):
    use_tts = tts

    async def event_generator():
        try:
            yield "data: " + json.dumps({"activity": {"event": "request_received", "message": "Processing request..."}}) + "\n\n"

            if "TTCAMTOKENTT" in prompt:
                # Clear token marker and isolate prompt text
                clean_prompt = prompt.replace("TTCAMTOKENTT", "").strip()
                file_path = os.path.join(config.DIRS["workspace_uploads"], "webcam.jpg")
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                    analysis = await vision_service.analyze_image(img_bytes, clean_prompt)
                    yield "data: " + json.dumps({"chunk": analysis}) + "\n\n"
                    return

            # 0. Retrieve conversational context
            context = await memory_service.get_context(session_id=session_id)

            # 1. Classify intent and get execution plan
            plan = await brain_service.classify_and_plan(prompt)
            
            # 2. Check if there are tasks to execute
            if plan.intent in ["task", "research", "vision"] and plan.execution_plan:
                yield "data: " + json.dumps({"activity": {"event": "task_plan", "message": "Executing task plan..."}}) + "\n\n"
                
                event_queue = asyncio.Queue()
                
                async def execute_tasks():
                    try:
                        await task_executor.execute_plan(plan.execution_plan, event_queue)
                    except Exception as e:
                        await event_queue.put({"type": "error", "text": str(e)})
                    finally:
                        await event_queue.put({"type": "_exec_done"})

                async def run_execution():
                    try:
                        await execute_tasks()
                    finally:
                        await event_queue.put({"type": "done"})

                asyncio.create_task(run_execution())
                
                exec_done = False
                active_tts_tasks = 0
                response_chunks = []
                
                while not (exec_done and active_tts_tasks == 0):
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        if active_tts_tasks == 0:
                            break
                    elif item["type"] == "_exec_done":
                        exec_done = True
                    elif item["type"] == "chunk":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64})
                        asyncio.create_task(bg_tts(item["text"]))
                    elif item["type"] == "audio_b64":
                        active_tts_tasks -= 1
                        if item["data"]:
                            yield "data: " + json.dumps({"audio": item["data"]}) + "\n\n"
                    elif item["type"] == "task_status":
                        yield "data: " + json.dumps({"activity": {"event": item.get('status'), "message": item.get('step')}}) + "\n\n"
                    elif item["type"] == "search_results":
                        raw_ans = item.get("answer", "")
                        distilled_ans = await _distill_answer(raw_ans, item["query"])
                        if use_tts:
                            await event_queue.put({"type": "tts_sentence", "text": distilled_ans})
                        response_chunks.append(distilled_ans)
                        yield "data: " + json.dumps({"chunk": distilled_ans}) + "\n\n"
                        yield "data: " + json.dumps({
                            "search_results": {
                                "query": item["query"],
                                "answer": distilled_ans,
                                "results": item["results"]
                            }
                        }) + "\n\n"
                    elif item["type"] == "token":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "error":
                        yield "data: " + json.dumps({"error": item["text"]}) + "\n\n"
                        
                full_response = "".join(response_chunks)
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

@app.post("/chat/victor/stream")
async def post_stream_endpoint(payload: ChatPayload):
    prompt = payload.message  # Map payload.message directly to our internal prompt execution logic
    session_id = payload.session_id or "default"
    use_tts = payload.tts or False

    async def event_generator():
        is_thinking = False
        try:
            yield "data: " + json.dumps({"activity": {"event": "request_received", "message": "Processing request..."}}) + "\n\n"

            if "TTCAMTOKENTT" in prompt:
                # Clear token marker and isolate prompt text
                clean_prompt = prompt.replace("TTCAMTOKENTT", "").strip()
                file_path = os.path.join(config.DIRS["workspace_uploads"], "webcam.jpg")
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                    analysis = await vision_service.analyze_image(img_bytes, clean_prompt)
                    yield "data: " + json.dumps({"chunk": analysis}) + "\n\n"
                    return

            # 0. Retrieve conversational context
            context = await memory_service.get_context(session_id=session_id)

            # 1. Classify intent and get execution plan
            plan = await brain_service.classify_and_plan(prompt)
            
            # 2. Check if there are tasks to execute
            if plan.intent in ["task", "research", "vision"] and plan.execution_plan:
                yield "data: " + json.dumps({"activity": {"event": "task_plan", "message": "Executing task plan..."}}) + "\n\n"
                
                event_queue = asyncio.Queue()
                
                async def execute_tasks():
                    try:
                        await task_executor.execute_plan(plan.execution_plan, event_queue)
                    except Exception as e:
                        await event_queue.put({"type": "error", "text": str(e)})
                    finally:
                        await event_queue.put({"type": "_exec_done"})

                async def run_execution():
                    try:
                        await execute_tasks()
                    finally:
                        await event_queue.put({"type": "done"})

                asyncio.create_task(run_execution())
                
                exec_done = False
                active_tts_tasks = 0
                response_chunks = []
                
                while not (exec_done and active_tts_tasks == 0):
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        if active_tts_tasks == 0:
                            break
                    elif item["type"] == "_exec_done":
                        exec_done = True
                    elif item["type"] == "chunk":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64})
                        asyncio.create_task(bg_tts(item["text"]))
                    elif item["type"] == "audio_b64":
                        active_tts_tasks -= 1
                        if item["data"]:
                            yield "data: " + json.dumps({"audio": item["data"]}) + "\n\n"
                    elif item["type"] == "search_results":
                        raw_ans = item.get("answer", "")
                        distilled_ans = await _distill_answer(raw_ans, item["query"])
                        if use_tts:
                            await event_queue.put({"type": "tts_sentence", "text": distilled_ans})
                        response_chunks.append(distilled_ans)
                        yield "data: " + json.dumps({"chunk": distilled_ans}) + "\n\n"
                        yield "data: " + json.dumps({"search_results": {"query": item["query"], "answer": distilled_ans, "results": item["results"]}}) + "\n\n"
                    elif item["type"] == "token":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "error":
                        yield "data: " + json.dumps({"error": item["text"]}) + "\n\n"
                        
                full_response = "".join(response_chunks)
                await memory_service.save_interaction(session_id, prompt, full_response)
            else:
                yield "data: " + json.dumps({"activity": {"event": "chat", "message": "Thinking..."}}) + "\n\n"
                messages = [
                    {"role": "system", "content": f"You are {config.ASSISTANT_NAME}, a highly capable AI tactical assistant.\n\n{context}"},
                    {"role": "user", "content": prompt}
                ]
                full_response_parts = []
                event_queue = asyncio.Queue()

                async def consume_chat_stream():
                    try:
                        sentence_buffer = ""
                        async for chunk in ai_service.stream_chat_completion(messages):
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

                async def run_chat():
                    try:
                        await consume_chat_stream()
                    finally:
                        await event_queue.put({"type": "done"})

                asyncio.create_task(run_chat())

                ai_done = False
                active_tts_tasks = 0

                while not (ai_done and active_tts_tasks == 0):
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        break
                    elif item["type"] == "_ai_done":
                        ai_done = True
                    elif item["type"] == "chunk":
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64})
                        asyncio.create_task(bg_tts(item["text"]))
                    elif item["type"] == "audio_b64":
                        active_tts_tasks -= 1
                        if item["data"]:
                            yield "data: " + json.dumps({"audio": item["data"]}) + "\n\n"
                    elif item["type"] == "token":
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "error":
                        yield "data: " + json.dumps({"error": item["text"]}) + "\n\n"

                full_response = "".join(full_response_parts)
                await memory_service.save_interaction(session_id, prompt, full_response)
                
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            
        finally:
            yield "data: " + json.dumps({"done": True}) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(config.DIRS["workspace_uploads"], "webcam.jpg")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    return {"status": "success", "filename": "webcam.jpg"}

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

@app.get("/app/audio/{file_name}")
async def silent_audio_placeholder(file_name: str):
    return {"status": "silent_mode"}

# Mount frontend at the root route to serve cleanly
app.mount("/", StaticFiles(directory=config.DIRS["frontend"], html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
