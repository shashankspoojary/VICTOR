import asyncio
import logging
import os
from pathlib import Path
from rich.console import Console

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from app.utils.key_rotation import llm_key_manager
from app.utils.retry import async_retry
from app.utils.time_info import get_temporal_string
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService

console = Console()

# --- Old Utility Mock Tests ---
# @async_retry(retries=3, initial_delay=0.5, backoff_factor=1.5, key_manager=llm_key_manager)
# async def fetch_llm_response_mock():
#     current_key = llm_key_manager.get_current_key()
#     console.print(f"[bold cyan]Attempting fetch with key:[/bold cyan] {current_key}")
#     
#     # Simulate a network glitch or rate limit (transient error)
#     raise Exception("429 Rate Limit Exceeded")
# 
# async def test_utilities_mock():
#     console.print("\n[bold green]--- Testing Async Retry & Key Rotation (Mock) ---[/bold green]")
#     original_keys = llm_key_manager.keys.copy()
#     original_index = llm_key_manager.current_index
#     
#     llm_key_manager.keys = ["dummy_key_A", "dummy_key_B", "dummy_key_C"]
#     llm_key_manager.current_index = 0
#     
#     try:
#         await fetch_llm_response_mock()
#     except Exception as e:
#         console.print(f"\n[bold red]Function finally failed after retries with error:[/bold red] {e}")
#         
#     console.print(f"\n[bold green]Final active key after retries:[/bold green] {llm_key_manager.get_current_key()}")
#     
#     llm_key_manager.keys = original_keys
#     llm_key_manager.current_index = original_index


async def main():
    console.print("[bold green]--- Starting VICTOR Memory Service Test ---[/bold green]")
    
    # 1. Setup sample learning data
    learning_dir = Path("database/learning_data")
    learning_dir.mkdir(parents=True, exist_ok=True)
    
    with open(learning_dir / "userdata.txt", "w", encoding="utf-8") as f:
        f.write("Owner: Shashank, Role: Developer")
        
    with open(learning_dir / "victor_personality.txt", "w", encoding="utf-8") as f:
        f.write("Identity: VICTOR, Style: Tactical, Concise")
        
    with open(learning_dir / "system_context.txt", "w", encoding="utf-8") as f:
        f.write("Environment: Windows, Task: Milestone 4 implementation")
        
    with open(learning_dir / "custom_notes.txt", "w", encoding="utf-8") as f:
        f.write("Notes: Prefer flat-file memory over vector databases.")

    # 2. Instantiate MemoryService
    memory_service = MemoryService()
    
    # 3. Add some dummy chat history for testing
    session_id = "test_session_001"
    memory_service.add_message(session_id, "user", "Hello VICTOR")
    memory_service.add_message(session_id, "assistant", "Acknowledged. Standing by.")
    
    # 4. Build Context
    current_query = "What is my role?"
    context_payload = memory_service.build_context(session_id, current_query)
    
    # 5. Print out the aggregated payload cleanly using rich
    console.print("\n[bold cyan]Aggregated Context Payload:[/bold cyan]")
    console.print_json(data=context_payload)
    
    console.print("\n[bold green]--- Test Complete ---[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
