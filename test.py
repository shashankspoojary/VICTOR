import asyncio
from rich.console import Console
from app.utils.time_info import get_current_time_context
from app.services.ai_service import ai_service
from app.services.brain_service import brain_service
from app.utils.key_rotation import groq_rotator
from app.services.task_executor import task_executor
import config

console = Console()

async def run_test_1():
    console.print("\n[bold yellow]--- Test 1: Stream Cleanup (Filtering <think> tags) ---[/bold yellow]")
    time_context = get_current_time_context()
    
    prompt = "Explain how a black hole forms. Please wrap your step-by-step thinking inside <think> and </think> tags before giving the final answer."
    messages = [
        {"role": "system", "content": f"You are {config.ASSISTANT_NAME}, a highly advanced AI assistant. Current time context: {time_context}"},
        {"role": "user", "content": prompt}
    ]
    
    console.print(f"[bold green]User:[/bold green] {prompt}")
    
    current_key_idx = groq_rotator.current_index
    console.print(f"[bold magenta]VICTOR (Key Index {current_key_idx}):[/bold magenta] ", end="")
    
    try:
        async for chunk in ai_service.stream_chat_completion(messages):
            console.print(chunk, end="")
        console.print()
    except Exception as e:
        console.print(f"\n[bold red]Error during test 1:[/bold red] {e}")

async def run_test_2():
    console.print("\n[bold yellow]--- Test 2: Brain Routing (Execution Plan) ---[/bold yellow]")
    prompt = "Play lo-fi beats on YouTube, and look up the current news on space exploration."
    
    console.print(f"[bold green]User Input:[/bold green] {prompt}")
    console.print("[cyan]Classifying and planning...[/cyan]")
    
    try:
        plan = await brain_service.classify_and_plan(user_input=prompt)
        console.print("[bold green]Execution Plan Received:[/bold green]")
        console.print(f"Intent: [bold magenta]{plan.intent}[/bold magenta]")
        console.print("Steps:")
        for i, step in enumerate(plan.execution_plan, 1):
            console.print(f"  {i}. {step}")
            
        await task_executor.execute_plan(plan.execution_plan)
    except Exception as e:
        console.print(f"\n[bold red]Error during test 2:[/bold red] {e}")

async def main():
    console.print("[bold cyan]Initializing VICTOR System Test...[/bold cyan]")
    # await run_test_1()
    await run_test_2()

if __name__ == "__main__":
    asyncio.run(main())
