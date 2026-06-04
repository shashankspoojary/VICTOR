import asyncio
import logging
import sys
from rich.console import Console
from rich.panel import Panel
from app.services.realtime_service import RealtimeService

# Setup basic logging
# Fix for windows charmap encode errors
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console = Console()

async def main():
    console.print("[bold green]--- Starting VICTOR Realtime Service Test ---[/bold green]")
    
    realtime_service = RealtimeService()
    query = "Latest developments in space exploration 2026"
    
    console.print(f"\n[bold cyan]Executing search_web[/bold cyan] -> Query: '{query}'")
    try:
        result = await realtime_service.search_web(query)
        console.print(Panel(result, title="[bold green]Realtime Search Context[/bold green]", expand=False))
    except Exception as e:
        console.print(f"[bold red]Search failed: {e}[/bold red]")
    
    console.print("\n[bold green]--- Test Complete ---[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
