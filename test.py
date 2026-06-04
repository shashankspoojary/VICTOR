import asyncio
import logging
import sys
from rich.console import Console
from rich.panel import Panel
from app.services.brain_service import BrainService

# Setup basic logging
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console = Console()

async def main():
    console.print("[bold green]--- Starting VICTOR Master Interaction Loop Test ---[/bold green]")
    
    brain_service = BrainService()
    session_id = "test_session_001"
    query = "VICTOR, check current space events for this year and summarize what SpaceX is planning to do."
    
    console.print(f"\n[bold cyan]Executing Master Query[/bold cyan] -> '{query}'")
    
    try:
        response = await brain_service.execute_query(session_id, query)
        console.print(Panel(response, title="[bold green]VICTOR Synthesized Response[/bold green]", expand=False))
    except Exception as e:
        console.print(f"[bold red]Execution failed: {e}[/bold red]")
        
    console.print("\n[bold cyan]--- Testing Vision Service ---[/bold cyan]")
    # 2x2 pixel transparent PNG (Groq requires at least 2x2)
    blank_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVQIW2NkYGD4z8DAwMgAI0AMDA4QAoEM2QAAAABJRU5ErkJggg=="
    vision_query = "TTCAMTOKENTT Identify if this visual stream is operational."
    
    console.print(f"[bold cyan]Executing Vision Query[/bold cyan] -> '{vision_query}'")
    try:
        vision_response = await brain_service.execute_query(session_id, vision_query, base64_image=blank_image_b64)
        console.print(Panel(vision_response, title="[bold green]VICTOR Vision Response[/bold green]", expand=False))
    except Exception as e:
        console.print(f"[bold red]Vision Execution failed: {e}[/bold red]")
    
    console.print("\n[bold green]--- Test Complete ---[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
