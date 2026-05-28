# run.py
import sys
import asyncio

# Prevent Uvicorn from downgrading the event loop on Windows
if sys.platform == "win32":
    asyncio.WindowsSelectorEventLoopPolicy = asyncio.WindowsProactorEventLoopPolicy
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[INFRASTRUCTURE] Master Process: Uvicorn event loop downgrade blocked.")

import uvicorn

if __name__ == "__main__":
    # Runs the VICTOR FastAPI backend on port 8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)