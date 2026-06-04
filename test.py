import asyncio
import logging
from rich.console import Console

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from app.utils.key_rotation import llm_key_manager
from app.utils.retry import async_retry
from app.utils.time_info import get_temporal_string
from app.services.ai_service import AIService

console = Console()

# --- Old Utility Mock Tests ---
@async_retry(retries=3, initial_delay=0.5, backoff_factor=1.5, key_manager=llm_key_manager)
async def fetch_llm_response_mock():
    current_key = llm_key_manager.get_current_key()
    console.print(f"[bold cyan]Attempting fetch with key:[/bold cyan] {current_key}")
    
    # Simulate a network glitch or rate limit (transient error)
    raise Exception("429 Rate Limit Exceeded")

async def test_utilities_mock():
    console.print("\n[bold green]--- Testing Async Retry & Key Rotation (Mock) ---[/bold green]")
    original_keys = llm_key_manager.keys.copy()
    original_index = llm_key_manager.current_index
    
    llm_key_manager.keys = ["dummy_key_A", "dummy_key_B", "dummy_key_C"]
    llm_key_manager.current_index = 0
    
    try:
        await fetch_llm_response_mock()
    except Exception as e:
        console.print(f"\n[bold red]Function finally failed after retries with error:[/bold red] {e}")
        
    console.print(f"\n[bold green]Final active key after retries:[/bold green] {llm_key_manager.get_current_key()}")
    
    llm_key_manager.keys = original_keys
    llm_key_manager.current_index = original_index


async def main():
    console.print("[bold green]--- Starting VICTOR Core & AI Service Test ---[/bold green]")
    
    # Test Time Info
    temporal_str = get_temporal_string()
    console.print(f"[bold yellow]Temporal Context:[/bold yellow] {temporal_str}")
    
    # Uncomment to test the mocked utilities
    # await test_utilities_mock()
    
    console.print("\n[bold green]--- Testing AI Service (Real-time Generation) ---[/bold green]")
    ai_service = AIService()
    prompt = "Hello VICTOR, confirm your primary operational model designation."
    console.print(f"[bold blue]Sending Prompt:[/bold blue] {prompt}")
    
    try:
        response = await ai_service.generate_text(
            prompt=prompt,
            system_prompt="You are VICTOR, an advanced AI assistant. Keep responses brief and precise."
        )
        console.print(f"\n[bold magenta]VICTOR Response:[/bold magenta]\n{response}")
    except Exception as e:
        console.print(f"\n[bold red]AI Service failed:[/bold red] {e}")
        
    console.print("\n[bold green]--- Test Complete ---[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
