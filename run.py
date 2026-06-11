import sys
import os
from rich.console import Console
from rich.table import Table

# Initialize rich console
console = Console()

def check_env_variables():
    """Verify all required environment variables are present and not empty."""
    required_keys = [
        "PORT", "HOST",
        "GROQ_API_KEY1", "GROQ_API_KEY2", "GROQ_API_KEY3",
        "TAVILY_API_KEY", "TAVILY_API_KEY_2", "TAVILY_API_KEY_3",
        "GROQ_VLM_API_KEY_1", "GROQ_VLM_API_KEY_2", "GROQ_VLM_API_KEY_3",
        "GROQ_MODEL", "GROQ_VLM_MODEL",
        "TTS_VOICE", "TTS_RATE",
        "ASSISTANT_NAME", "VICTOR_USER_TITLE", "VICTOR_OWNER_NAME"
    ]

    missing_or_empty = []
    
    for key in required_keys:
        val = os.getenv(key)
        if not val or not str(val).strip():
            missing_or_empty.append(key)
            
    if missing_or_empty:
        table = Table(
            title="[bold red]Startup Check Failed: Missing Environment Variables[/bold red]", 
            show_header=True, 
            header_style="bold magenta",
            title_justify="left"
        )
        table.add_column("Environment Variable", style="cyan", min_width=25)
        table.add_column("Status", justify="center", style="red")
        
        for key in missing_or_empty:
            table.add_row(key, "MISSING OR EMPTY")
            
        console.print(table)
        console.print("\n[bold yellow]Action Required:[/bold yellow] Please configure these variables in your [cyan].env[/cyan] file before starting VICTOR.")
        sys.exit(1)

def main():
    console.print("\n[bold cyan]Initializing VICTOR Core System...[/bold cyan]")
    
    # Importing config automatically creates directories and loads the .env file
    try:
        import config
    except Exception as e:
        console.print(f"[bold red]Failed to load configuration:[/bold red] {e}")
        sys.exit(1)
        
    # Perform startup validation checks
    check_env_variables()
    
    # Success message
    console.print("[bold green][SUCCESS] VICTOR Core System Initialized Successfully[/bold green]\n")
    
    # Start the server
    console.print(f"[bold green]Dashboard is live at http://{config.HOST}:{config.PORT}[/bold green]")
    
    # Automatically open the browser in Google Chrome
    import threading
    import time
    import webbrowser

    def open_browser():
        time.sleep(1.5)  # Give uvicorn a moment to start and bind to the port
        host = "127.0.0.1" if config.HOST == "0.0.0.0" else config.HOST
        url = f"http://{host}:{config.PORT}"
        
        opened = False
        # Try standard paths for Google Chrome on Windows
        for chrome_path in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]:
            if os.path.exists(chrome_path):
                try:
                    webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
                    webbrowser.get('chrome').open(url)
                    opened = True
                    break
                except Exception:
                    pass
        
        if not opened:
            try:
                # Try registered chrome name
                webbrowser.get('chrome').open(url)
            except Exception:
                # Fallback to system default browser
                webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)

if __name__ == "__main__":
    main()
