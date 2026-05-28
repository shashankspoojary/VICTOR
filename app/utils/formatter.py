from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()



def print_system_status(status: str):
    console.print(f"[bold yellow]System:[/bold yellow] {status}")

def print_user_prompt():
    return console.input("[bold green]User:[/bold green] ")

def format_bot_message(text: str) -> Markdown:
    return Markdown(text)