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
    # 2x2 pixel JPEG (Groq requires at least 2x2 and vision_service uses image/jpeg)
    blank_image_b64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oAMBAAIRAxEAPwDi6KKK+ZP3E//Z"
    vision_query = "TTCAMTOKENTT Identify if this visual stream is operational."
    
    console.print(f"[bold cyan]Executing Vision Query[/bold cyan] -> '{vision_query}'")
    try:
        vision_response = await brain_service.execute_query(session_id, vision_query, base64_image=blank_image_b64)
        console.print(Panel(vision_response, title="[bold green]VICTOR Vision Response[/bold green]", expand=False))
    except Exception as e:
        console.print(f"[bold red]Vision Execution failed: {e}[/bold red]")

    console.print("\n[bold cyan]--- Testing Task Executor ---[/bold cyan]")
    task_query = "VICTOR, open my browser to https://example.com"
    console.print(f"[bold cyan]Executing Task Query[/bold cyan] -> '{task_query}'")
    try:
        task_response = await brain_service.execute_query(session_id, task_query)
        console.print(Panel(task_response, title="[bold green]VICTOR Task Response[/bold green]", expand=False))
    except Exception as e:
        console.print(f"[bold red]Task Execution failed: {e}[/bold red]")
    
    console.print("\n[bold green]--- Test Complete ---[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
