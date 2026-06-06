import asyncio
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Ensure the root directory is on the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from app.services.brain_service import brain_service
from app.services.task_executor import task_executor
from app.services.ai_service import ai_service

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

@app.get("/api/stream")
async def stream_endpoint(prompt: str):
    async def event_generator():
        try:
            # 1. Classify intent and get execution plan
            plan = await brain_service.classify_and_plan(prompt)
            
            # 2. Check if there are tasks to execute
            if plan.intent in ["task", "research", "vision"] and plan.execution_plan:
                # Yield task event message
                task_msg = json.dumps({"type": "task", "status": "running", "plan": plan.execution_plan})
                yield f"data: {task_msg}\n\n"
                
                event_queue = asyncio.Queue()
                
                # Stream conversational acknowledgment token-by-token
                messages = [
                    {"role": "system", "content": f"You are {config.ASSISTANT_NAME}. Acknowledge the user's request and state you are executing the tasks. Keep it very short, tactical, and professional."},
                    {"role": "user", "content": prompt}
                ]
                
                ai_stream = ai_service.stream_chat_completion(messages)
                
                async def consume_ai_stream():
                    try:
                        async for chunk in ai_stream:
                            await event_queue.put({"type": "token", "text": chunk})
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
                    else:
                        yield f"data: {json.dumps(item)}\n\n"
            else:
                # Regular chat
                messages = [
                    {"role": "system", "content": f"You are {config.ASSISTANT_NAME}, a highly capable AI tactical assistant."},
                    {"role": "user", "content": prompt}
                ]

                async for chunk in ai_service.stream_chat_completion(messages):
                    yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
            
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Mount frontend at the root route to serve cleanly
app.mount("/", StaticFiles(directory=config.DIRS["frontend"], html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
