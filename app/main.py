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
    auto_open_tabs: Optional[bool] = False

async def synthesize_speech_to_b64(text: str) -> Optional[str]:
    # 1. Scrub thinking blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    if "<think>" in text:
        text = text.split("<think>")[0]
        
    # 2. Scrub markdown tables, pipes, separators, and dashes
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip table separator lines or dashes
        if re.match(r'^[|\s\-:+\u2014]+$', stripped):
            continue
        cleaned_line = stripped.replace("|", " ").strip()
        if cleaned_line:
            cleaned_lines.append(cleaned_line)
    text = " ".join(cleaned_lines)
    
    # 3. Clean remaining formatting markers
    text = text.replace("*", "").replace("`", "").replace("#", "").strip()
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text:
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

def select_filler_phrase(intent: str, prompt: str) -> Optional[str]:
    import random
    p = prompt.lower()
    if intent == "research":
        if "weather" in p or "temperature" in p:
            return "Checking the weather, give me a second."
        if "news" in p or "latest" in p:
            return "Let me fetch the latest updates, hold on."
        return random.choice(["Alright, give me a second.", "Got it, hold on.", "Give me a moment."])
    elif intent == "task":
        if "open" in p or "launch" in p:
            return "On it right now."
        if "play" in p or "music" in p or "song" in p or "youtube" in p:
            return "Got it, hold on."
        if "volume" in p or "brightness" in p or "mute" in p:
            return "Ok, hold on."
        return random.choice(["I am working on it.", "On it right now.", "Ok, hold on."])
    elif intent == "vision":
        return "Give me a moment."
    elif intent == "chat":
        # Check if it looks like an informational or analytical question
        if any(w in p for w in ["what", "how", "why", "who", "where", "explain"]):
            return random.choice(["Alright, give me a second.", "Give me a moment."])
    return None

# Fast non-thinking model for distillation tasks (avoids empty-output errors from thinking models)
_FAST_MODEL = "llama-3.3-70b-versatile"

async def _dual_distill(raw_text: str, query: str) -> tuple:
    """Single AI call returning (chat_answer, sidebar_answer) — one round-trip instead of two."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are VICTOR's data purification engine.\n"
                "Given raw search results, return a JSON object with exactly two fields:\n"
                "1. \"chat\": A plain-text response that will be spoken aloud to the user. "
                "CRITICAL: If the user asks a simple fact (e.g., value of dollar, bitcoin, weather, age), give a short 1-2 line direct answer. "
                "If the user asks a complex question requiring a longer explanation (e.g., world news, about a company, advanced topics), "
                "provide a detailed, conversational summary (up to 3 paragraphs). "
                "No markdown, no asterisks, no tables in the \"chat\" field.\n"
                "2. \"sidebar\": A clean structured markdown summary (max 250 words). "
                "Use bold for key values, a small table for comparisons, or bullets for lists. "
                "Strip all website boilerplate, ads, and SEO noise.\n\n"
                "CRITICAL INSTRUCTIONS FOR ACCURACY:\n"
                "- Compare all sources. If sources show varying prices or values for a product, provide the typical price range instead of saying it's not stated.\n"
                "- If some sources list outdated values (e.g., old exchange rates) and authoritative sources show newer live rates, report the newer rate.\n"
                "- Do not hallucinate. Ensure each source's values listed match exactly what that source reported in the snippet.\n"
                "Return ONLY valid JSON — no extra text outside the JSON object."
            )
        },
        {"role": "user", "content": f"Question: {query}\n\nSearch Results:\n{raw_text[:6000]}"}
    ]
    try:
        result = await ai_service.get_chat_completion(
            messages,
            model=_FAST_MODEL,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(result or "{}")
        chat_ans = (data.get("chat") or "").strip()
        sidebar_ans = (data.get("sidebar") or "").strip()
        # Fallback if either field is empty
        if not chat_ans:
            chat_ans = sidebar_ans[:200].strip() if sidebar_ans else raw_text[:200].strip()
        if not sidebar_ans:
            sidebar_ans = chat_ans
        return chat_ans, sidebar_ans
    except Exception as e:
        print(f"[_dual_distill] Error: {e}")
        fallback = raw_text[:300].strip()
        return fallback, fallback

@app.get("/api/stream")
async def get_stream_endpoint(prompt: str, session_id: Optional[str] = "default", tts: Optional[bool] = False, auto_open_tabs: Optional[bool] = False):
    use_tts = tts

    async def event_generator():
        try:
            yield "data: " + json.dumps({"activity": {"event": "request_received", "message": "Processing request..."}}) + "\n\n"

            if "TTCAMTOKENTT" in prompt:
                # Clear token marker and isolate prompt text
                clean_prompt = prompt.replace("TTCAMTOKENTT", "").strip() or "What do you see?"
                file_path = os.path.join(config.DIRS["workspace_uploads"], "webcam.jpg")
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                    if use_tts:
                        filler_phrase = "Give me a moment."
                        yield "data: " + json.dumps({"chunk": filler_phrase + "\n\n"}) + "\n\n"
                        filler_audio = await synthesize_speech_to_b64(filler_phrase)
                        if filler_audio:
                            yield "data: " + json.dumps({"audio": filler_audio}) + "\n\n"
                    analysis = await vision_service.analyze_image(img_bytes, clean_prompt)
                    yield "data: " + json.dumps({"chunk": analysis}) + "\n\n"
                    if use_tts and analysis:
                        sentences = re.split(
                            r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                            r'(?<!\b[a-zA-Z]\.)'
                            r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                            r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                            analysis
                        )
                        audio_queue = asyncio.Queue()
                        active_tasks = 0
                        
                        async def bg_tts(txt, idx):
                            b64 = await synthesize_speech_to_b64(txt)
                            await audio_queue.put((idx, b64))
                            
                        idx = 0
                        for sentence in sentences:
                            clean_sentence = sentence.replace("*", "").replace("#", "").strip()
                            if clean_sentence:
                                asyncio.create_task(bg_tts(clean_sentence, idx))
                                idx += 1
                                active_tasks += 1
                                
                        next_idx = 0
                        audio_buffer = {}
                        while active_tasks > 0:
                            item_idx, b64 = await audio_queue.get()
                            audio_buffer[item_idx] = b64
                            while next_idx in audio_buffer:
                                chunk_b64 = audio_buffer.pop(next_idx)
                                if chunk_b64:
                                    yield "data: " + json.dumps({"audio": chunk_b64}) + "\n\n"
                                next_idx += 1
                                active_tasks -= 1
                else:
                    yield "data: " + json.dumps({"chunk": "I couldn't access the camera image. Please ensure your camera is active and try again."}) + "\n\n"
                yield "data: " + json.dumps({"done": True}) + "\n\n"
                return


            # 0 & 1. Fetch context + classify intent concurrently (independent ops)
            context, plan = await asyncio.gather(
                memory_service.get_context(session_id=session_id),
                brain_service.classify_and_plan(prompt)
            )
            from app.utils.file_pruning import prune_context
            context = prune_context(context)
            
            if use_tts:
                filler_phrase = select_filler_phrase(plan.intent, prompt)
                if filler_phrase:
                    yield "data: " + json.dumps({"chunk": filler_phrase + "\n\n"}) + "\n\n"
                    filler_audio = await synthesize_speech_to_b64(filler_phrase)
                    if filler_audio:
                        yield "data: " + json.dumps({"audio": filler_audio}) + "\n\n"
            
            # 2. Check if there are tasks to execute
            if plan.intent in ["task", "research", "vision"] and plan.execution_plan:
                yield "data: " + json.dumps({"activity": {"event": "task_plan", "message": "Executing task plan..."}}) + "\n\n"
                
                event_queue = asyncio.Queue()
                
                async def execute_tasks():
                    try:
                        await task_executor.execute_plan(plan.execution_plan, event_queue, auto_open_tabs=auto_open_tabs)
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
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
                tts_index = 0
                next_audio_idx_to_yield = 0
                audio_buffer = {}
                response_chunks = []
                
                while True:
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        if active_tts_tasks == 0 and event_queue.empty():
                            break
                        else:
                            await event_queue.put({"type": "done"})
                            await asyncio.sleep(0.02)
                    elif item["type"] == "_exec_done":
                        exec_done = True
                    elif item["type"] == "chunk":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt, idx):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64, "idx": idx})
                        asyncio.create_task(bg_tts(item["text"], tts_index))
                        tts_index += 1
                    elif item["type"] == "audio_b64":
                        idx = item["idx"]
                        audio_buffer[idx] = item["data"]
                        while next_audio_idx_to_yield in audio_buffer:
                            b64 = audio_buffer.pop(next_audio_idx_to_yield)
                            if b64:
                                yield "data: " + json.dumps({"audio": b64}) + "\n\n"
                            next_audio_idx_to_yield += 1
                            active_tts_tasks -= 1
                    elif item["type"] == "task_status":
                        yield "data: " + json.dumps({"activity": {"event": item.get('status'), "message": item.get('step')}}) + "\n\n"
                    elif item["type"] == "search_results":
                        raw_answer = item["answer"]
                        
                        # Single AI call → both chat and sidebar answers at once
                        chat_answer, sidebar_answer = await _dual_distill(raw_answer, item["query"])
                        
                        # 1. Short direct answer → chat bubble only
                        response_chunks.append(chat_answer)
                        yield "data: " + json.dumps({"chunk": chat_answer}) + "\n\n"
                        
                        # 2. Full structured breakdown → References sidebar only
                        yield "data: " + json.dumps({
                            "search_results": {
                                "query": item["query"],
                                "answer": sidebar_answer,
                                "results": item["results"]
                            }
                        }) + "\n\n"
                        
                        # 3. Same short answer → TTS voice engine
                        if use_tts and chat_answer:
                            sentences = re.split(
                                r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                                r'(?<!\b[a-zA-Z]\.)'
                                r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                                r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                                chat_answer
                            )
                            for sentence in sentences:
                                clean_sentence = sentence.replace("*", "").replace("#", "").strip()
                                if clean_sentence:
                                    await event_queue.put({"type": "tts_sentence", "text": clean_sentence})
                    elif item["type"] == "token":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                        if use_tts and item["text"].strip():
                            sentences = re.split(
                                r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                                r'(?<!\b[a-zA-Z]\.)'
                                r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                                r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                                item["text"]
                            )
                            for sentence in sentences:
                                clean_sentence = sentence.replace("*", "").replace("#", "").strip()
                                if clean_sentence:
                                    await event_queue.put({"type": "tts_sentence", "text": clean_sentence})
                    elif item["type"] == "actions":
                        yield "data: " + json.dumps({"actions": item["actions"]}) + "\n\n"
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
                                # Clean completed think blocks
                                sentence_buffer = re.sub(r'<think>.*?</think>', '', sentence_buffer, flags=re.DOTALL)
                                
                                active_buffer = sentence_buffer
                                if "<think>" in active_buffer:
                                    active_buffer = active_buffer.split("<think>")[0]
                                    
                                while True:
                                    match = re.search(
                                        r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                                        r'(?<!\b[a-zA-Z]\.)'
                                        r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                                        r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                                        active_buffer
                                    )
                                    if match:
                                        sentence = active_buffer[:match.end()].strip()
                                        sentence_buffer = sentence_buffer[match.end():]
                                        active_buffer = sentence_buffer
                                        if "<think>" in active_buffer:
                                            active_buffer = active_buffer.split("<think>")[0]
                                        
                                        if sentence:
                                            clean_sentence = re.sub(r'<think>.*?</think>', '', sentence, flags=re.DOTALL)
                                            clean_sentence = clean_sentence.replace("*", "").replace("#", "").strip()
                                            if clean_sentence:
                                                await event_queue.put({"type": "tts_sentence", "text": clean_sentence})
                                    else:
                                        break
                                            
                        if use_tts and sentence_buffer.strip():
                            final_text = re.sub(r'<think>.*?</think>', '', sentence_buffer, flags=re.DOTALL)
                            if "<think>" in final_text:
                                final_text = final_text.split("<think>")[0]
                            final_text = final_text.replace("*", "").replace("#", "").strip()
                            if final_text:
                                await event_queue.put({"type": "tts_sentence", "text": final_text})
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
                tts_index = 0
                next_audio_idx_to_yield = 0
                audio_buffer = {}

                while True:
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        if active_tts_tasks == 0 and event_queue.empty():
                            break
                        else:
                            await event_queue.put({"type": "done"})
                            await asyncio.sleep(0.02)
                    elif item["type"] == "_ai_done":
                        ai_done = True
                    elif item["type"] == "chunk":
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt, idx):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64, "idx": idx})
                        asyncio.create_task(bg_tts(item["text"], tts_index))
                        tts_index += 1
                    elif item["type"] == "audio_b64":
                        idx = item["idx"]
                        audio_buffer[idx] = item["data"]
                        while next_audio_idx_to_yield in audio_buffer:
                            b64 = audio_buffer.pop(next_audio_idx_to_yield)
                            if b64:
                                yield "data: " + json.dumps({"audio": b64}) + "\n\n"
                            next_audio_idx_to_yield += 1
                            active_tts_tasks -= 1
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

def extract_text_from_file(file_name: str, file_type: str, file_data_base64: str) -> str:
    """Extract text content from various file types uploaded in base64 format."""
    if not file_data_base64:
        return ""
        
    def limit_text(txt: str) -> str:
        max_chars = getattr(config, "MAX_EXTRACT_CHARS", 25000)
        if len(txt) > max_chars:
            return txt[:max_chars] + f"\n\n... [Content truncated to {max_chars} characters for context/rate limits] ..."
        return txt

    try:
        if "," in file_data_base64:
            file_data_base64 = file_data_base64.split(",")[1]
        import base64
        import io
        from pathlib import Path
        file_bytes = base64.b64decode(file_data_base64)
        ext = Path(file_name).suffix.lower()
        if len(file_bytes) > 10 * 1024 * 1024:
            return f"[File {file_name} is too large to extract text (limit: 10MB)]"
            
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                return limit_text(text)
            except Exception:
                try:
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    return limit_text(text)
                except Exception as e2:
                    return f"[Error parsing PDF: {e2}]"
        elif ext == ".docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(file_bytes))
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return limit_text("\n".join(text))
            except Exception as e:
                return f"[Error parsing Word Document: {e}]"
        elif ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
                df = pd.read_excel(io.BytesIO(file_bytes))
                return limit_text(df.to_string())
            except Exception as e:
                return f"[Error parsing Excel: {e}]"
        else:
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = file_bytes.decode("latin-1")
                except Exception as e:
                    return f"[Binary file '{file_name}' of size {len(file_bytes)} bytes, not readable as text]"
            return limit_text(text)
    except Exception as e:
        return f"[Failed to parse file '{file_name}': {str(e)}]"

@app.post("/chat/victor/stream")
async def post_stream_endpoint(payload: ChatPayload):
    prompt = payload.message  # Map payload.message directly to our internal prompt execution logic
    session_id = payload.session_id or "default"
    use_tts = payload.tts or False

    # Process and extract text from non-image uploaded files
    file_context = ""
    if payload.files:
        for file_info in payload.files:
            file_type = file_info.get("type", "")
            file_name = file_info.get("name", "")
            file_data = file_info.get("data", "")
            if not file_type.startswith("image/") and file_data:
                extracted = extract_text_from_file(file_name, file_type, file_data)
                if extracted:
                    file_context += f"\n\n--- Start of File: {file_name} ---\n{extracted}\n--- End of File: {file_name} ---\n"
    if file_context:
        prompt = f"{prompt}\n{file_context}"

    async def event_generator():
        is_thinking = False
        try:
            yield "data: " + json.dumps({"activity": {"event": "request_received", "message": "Processing request..."}}) + "\n\n"

            # Isolate the clean prompt text and check if VLM should be used
            clean_prompt = prompt.replace("TTCAMTOKENTT", "").strip()
            
            # Determine if we have any image input (direct payload base64, files, or fallback webcam file)
            img_bytes = None
            
            # 1. Try payload.imgbase64
            if payload.imgbase64:
                try:
                    b64_str = payload.imgbase64
                    if "," in b64_str:
                        b64_str = b64_str.split(",")[1]
                    img_bytes = base64.b64decode(b64_str)
                except Exception as e:
                    print(f"Error decoding payload.imgbase64: {e}")
            
            # 2. Try uploaded image files in payload.files
            if not img_bytes and payload.files:
                for file_info in payload.files:
                    file_type = file_info.get("type", "")
                    file_data = file_info.get("data", "")
                    if file_type.startswith("image/") and file_data:
                        try:
                            if "," in file_data:
                                file_data = file_data.split(",")[1]
                            img_bytes = base64.b64decode(file_data)
                            break # Use the first image file
                        except Exception as e:
                            print(f"Error decoding uploaded image file: {e}")
                            
            # 3. Fallback to webcam.jpg on disk if TTCAMTOKENTT in prompt but no direct bytes
            if not img_bytes and "TTCAMTOKENTT" in prompt:
                file_path = os.path.join(config.DIRS["workspace_uploads"], "webcam.jpg")
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            img_bytes = f.read()
                    except Exception as e:
                        print(f"Error reading webcam.jpg: {e}")

            # If we successfully resolved image bytes, run the vision service!
            if img_bytes:
                query_text = clean_prompt or "What do you see?"
                try:
                    # Let the frontend know we've started image analysis
                    yield "data: " + json.dumps({"activity": {"event": "vision_analysis", "message": "Analyzing image..."}}) + "\n\n"
                    
                    if use_tts:
                        filler_phrase = "Give me a moment."
                        yield "data: " + json.dumps({"chunk": filler_phrase + "\n\n"}) + "\n\n"
                        filler_audio = await synthesize_speech_to_b64(filler_phrase)
                        if filler_audio:
                            yield "data: " + json.dumps({"audio": filler_audio}) + "\n\n"
                    
                    analysis = await vision_service.analyze_image(img_bytes, query_text)
                    
                    # Stream the response chunk to the UI
                    yield "data: " + json.dumps({"chunk": analysis}) + "\n\n"
                    
                    # Save the interaction to memory
                    await memory_service.save_interaction(session_id, query_text, analysis)
                    
                    # Generate speech output for the response if TTS is enabled
                    if use_tts and analysis:
                        sentences = re.split(
                            r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                            r'(?<!\b[a-zA-Z]\.)'
                            r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                            r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                            analysis
                        )
                        audio_queue = asyncio.Queue()
                        active_tasks = 0
                        
                        async def bg_tts(txt, idx):
                            b64 = await synthesize_speech_to_b64(txt)
                            await audio_queue.put((idx, b64))
                            
                        idx = 0
                        for sentence in sentences:
                            clean_sentence = sentence.replace("*", "").replace("#", "").strip()
                            if clean_sentence:
                                asyncio.create_task(bg_tts(clean_sentence, idx))
                                idx += 1
                                active_tasks += 1
                                
                        next_idx = 0
                        audio_buffer = {}
                        while active_tasks > 0:
                            item_idx, b64 = await audio_queue.get()
                            audio_buffer[item_idx] = b64
                            while next_idx in audio_buffer:
                                chunk_b64 = audio_buffer.pop(next_idx)
                                if chunk_b64:
                                    yield "data: " + json.dumps({"audio": chunk_b64}) + "\n\n"
                                next_idx += 1
                                active_tasks -= 1
                except Exception as e:
                    yield "data: " + json.dumps({"chunk": f"Error during image analysis: {str(e)}"}) + "\n\n"
                yield "data: " + json.dumps({"done": True}) + "\n\n"
                return
                
            # If camera bypass token is present but we failed to find any image
            if "TTCAMTOKENTT" in prompt:
                yield "data: " + json.dumps({"chunk": "I couldn't access the camera image. Please ensure your camera is active and try again."}) + "\n\n"
                yield "data: " + json.dumps({"done": True}) + "\n\n"
                return


            # 0 & 1. Fetch context + classify intent concurrently (independent ops)
            context, plan = await asyncio.gather(
                memory_service.get_context(session_id=session_id),
                brain_service.classify_and_plan(prompt)
            )
            from app.utils.file_pruning import prune_context
            context = prune_context(context)
            
            if use_tts:
                filler_phrase = select_filler_phrase(plan.intent, prompt)
                if filler_phrase:
                    yield "data: " + json.dumps({"chunk": filler_phrase + "\n\n"}) + "\n\n"
                    filler_audio = await synthesize_speech_to_b64(filler_phrase)
                    if filler_audio:
                        yield "data: " + json.dumps({"audio": filler_audio}) + "\n\n"
            
            # 2. Check if there are tasks to execute
            if plan.intent in ["task", "research", "vision"] and plan.execution_plan:
                yield "data: " + json.dumps({"activity": {"event": "task_plan", "message": "Executing task plan..."}}) + "\n\n"
                
                event_queue = asyncio.Queue()
                
                async def execute_tasks():
                    try:
                        await task_executor.execute_plan(plan.execution_plan, event_queue, auto_open_tabs=payload.auto_open_tabs)
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
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
                tts_index = 0
                next_audio_idx_to_yield = 0
                audio_buffer = {}
                response_chunks = []
                
                while True:
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        if active_tts_tasks == 0 and event_queue.empty():
                            break
                        else:
                            await event_queue.put({"type": "done"})
                            await asyncio.sleep(0.02)
                    elif item["type"] == "_exec_done":
                        exec_done = True
                    elif item["type"] == "chunk":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt, idx):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64, "idx": idx})
                        asyncio.create_task(bg_tts(item["text"], tts_index))
                        tts_index += 1
                    elif item["type"] == "audio_b64":
                        idx = item["idx"]
                        audio_buffer[idx] = item["data"]
                        while next_audio_idx_to_yield in audio_buffer:
                            b64 = audio_buffer.pop(next_audio_idx_to_yield)
                            if b64:
                                yield "data: " + json.dumps({"audio": b64}) + "\n\n"
                            next_audio_idx_to_yield += 1
                            active_tts_tasks -= 1
                    elif item["type"] == "search_results":
                        raw_answer = item["answer"]
                        
                        # Single AI call → both chat and sidebar answers at once
                        chat_answer, sidebar_answer = await _dual_distill(raw_answer, item["query"])
                        
                        # 1. Short direct answer → chat bubble only
                        response_chunks.append(chat_answer)
                        yield "data: " + json.dumps({"chunk": chat_answer}) + "\n\n"
                        
                        # 2. Full structured breakdown → References sidebar only
                        yield "data: " + json.dumps({
                            "search_results": {
                                "query": item["query"],
                                "answer": sidebar_answer,
                                "results": item["results"]
                            }
                        }) + "\n\n"
                        
                        # 3. Same short answer → TTS voice engine
                        if use_tts and chat_answer:
                            sentences = re.split(
                                r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                                r'(?<!\b[a-zA-Z]\.)'
                                r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                                r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                                chat_answer
                            )
                            for sentence in sentences:
                                clean_sentence = sentence.replace("*", "").replace("#", "").strip()
                                if clean_sentence:
                                    await event_queue.put({"type": "tts_sentence", "text": clean_sentence})
                    elif item["type"] == "token":
                        response_chunks.append(item["text"])
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                        if use_tts and item["text"].strip():
                            sentences = re.split(
                                r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                                r'(?<!\b[a-zA-Z]\.)'
                                r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                                r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                                item["text"]
                            )
                            for sentence in sentences:
                                clean_sentence = sentence.replace("*", "").replace("#", "").strip()
                                if clean_sentence:
                                    await event_queue.put({"type": "tts_sentence", "text": clean_sentence})
                    elif item["type"] == "actions":
                        yield "data: " + json.dumps({"actions": item["actions"]}) + "\n\n"
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
                                # Clean completed think blocks
                                sentence_buffer = re.sub(r'<think>.*?</think>', '', sentence_buffer, flags=re.DOTALL)
                                
                                active_buffer = sentence_buffer
                                if "<think>" in active_buffer:
                                    active_buffer = active_buffer.split("<think>")[0]
                                    
                                while True:
                                    match = re.search(
                                        r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
                                        r'(?<!\b[a-zA-Z]\.)'
                                        r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
                                        r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
                                        active_buffer
                                    )
                                    if match:
                                        sentence = active_buffer[:match.end()].strip()
                                        sentence_buffer = sentence_buffer[match.end():]
                                        active_buffer = sentence_buffer
                                        if "<think>" in active_buffer:
                                            active_buffer = active_buffer.split("<think>")[0]
                                            
                                        if sentence:
                                            clean_sentence = re.sub(r'<think>.*?</think>', '', sentence, flags=re.DOTALL)
                                            clean_sentence = clean_sentence.replace("*", "").replace("#", "").strip()
                                            if clean_sentence:
                                                await event_queue.put({"type": "tts_sentence", "text": clean_sentence})
                                    else:
                                        break
                        if use_tts and sentence_buffer.strip():
                            final_text = re.sub(r'<think>.*?</think>', '', sentence_buffer, flags=re.DOTALL)
                            if "<think>" in final_text:
                                final_text = final_text.split("<think>")[0]
                            final_text = final_text.replace("*", "").replace("#", "").strip()
                            if final_text:
                                await event_queue.put({"type": "tts_sentence", "text": final_text})
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
                tts_index = 0
                next_audio_idx_to_yield = 0
                audio_buffer = {}

                while True:
                    item = await event_queue.get()
                    if item.get("type") == "done":
                        if active_tts_tasks == 0 and event_queue.empty():
                            break
                        else:
                            await event_queue.put({"type": "done"})
                            await asyncio.sleep(0.02)
                    elif item["type"] == "_ai_done":
                        ai_done = True
                    elif item["type"] == "chunk":
                        yield "data: " + json.dumps({"chunk": item["text"]}) + "\n\n"
                    elif item["type"] == "tts_sentence":
                        active_tts_tasks += 1
                        async def bg_tts(txt, idx):
                            b64 = await synthesize_speech_to_b64(txt)
                            await event_queue.put({"type": "audio_b64", "data": b64, "idx": idx})
                        asyncio.create_task(bg_tts(item["text"], tts_index))
                        tts_index += 1
                    elif item["type"] == "audio_b64":
                        idx = item["idx"]
                        audio_buffer[idx] = item["data"]
                        while next_audio_idx_to_yield in audio_buffer:
                            b64 = audio_buffer.pop(next_audio_idx_to_yield)
                            if b64:
                                yield "data: " + json.dumps({"audio": b64}) + "\n\n"
                            next_audio_idx_to_yield += 1
                            active_tts_tasks -= 1
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

class FocusTabPayload(BaseModel):
    query: str

@app.post("/api/focus_tab")
async def focus_tab_endpoint(payload: FocusTabPayload):
    success = task_executor.focus_tab_by_query(payload.query)
    return {"status": "success" if success else "failed"}

@app.get("/app/audio/{file_name}")
async def silent_audio_placeholder(file_name: str):
    return {"status": "silent_mode"}

# Mount frontend at the root route to serve cleanly
app.mount("/", StaticFiles(directory=config.DIRS["frontend"], html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
