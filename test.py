import asyncio
import logging
from rich.console import Console
from app.services.brain_service import BrainService

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console = Console()

async def run_test(brain_service: BrainService, session_id: str, query: str, test_name: str):
    console.print(f"\n[bold cyan]Starting {test_name}[/bold cyan] -> Query: '{query}'")
    result = await brain_service.route_intent(session_id, query)
    console.print(f"[bold green]{test_name} Output Payload:[/bold green]")
    console.print_json(data=result)

async def main():
    console.print("[bold green]--- Starting VICTOR Cognitive Routing Brain Test ---[/bold green]")
    
    brain_service = BrainService()
    session_id = "test_session_brain"
    
    # Run three parallel test executions
    await asyncio.gather(
        run_test(brain_service, session_id, "Can you look at this? TTCAMTOKENTT", "Test A"),
        run_test(brain_service, session_id, "Who won the latest Formula 1 race?", "Test B"),
        run_test(brain_service, session_id, "Explain how a binary search tree works.", "Test C")
    )
    
    console.print("\n[bold green]--- Test Complete ---[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
