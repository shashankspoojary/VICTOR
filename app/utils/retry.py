import asyncio
import inspect
from functools import wraps
from rich.console import Console

console = Console()

def with_retry_and_rotation(rotator, max_retries=6, base_delay=1.0):
    """
    Decorator that intercepts API calls. If a rate limit or timeout exception
    occurs, it calls the rotator to swap keys and retries the operation.
    Supports both async functions and async generators.
    """
    def decorator(func):
        if inspect.isasyncgenfunction(func):
            @wraps(func)
            async def async_gen_wrapper(*args, **kwargs):
                delay = base_delay
                for attempt in range(max_retries):
                    try:
                        async for item in func(*args, **kwargs):
                            yield item
                        return
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "rate limit" in error_msg or "timeout" in error_msg or "429" in error_msg or "503" in error_msg:
                            if attempt < max_retries - 1:
                                console.print(f"[bold red]API Error:[/bold red] Rate limit or Timeout. Retrying ({attempt + 1}/{max_retries}) after {delay}s...")
                                rotator.rotate_key()
                                await asyncio.sleep(delay)
                                delay *= 2
                            else:
                                console.print(f"[bold red]Max retries reached for {rotator.service_name}.[/bold red]")
                                raise
                        else:
                            raise
            return async_gen_wrapper
        else:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                delay = base_delay
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "rate limit" in error_msg or "timeout" in error_msg or "429" in error_msg or "503" in error_msg:
                            if attempt < max_retries - 1:
                                console.print(f"[bold red]API Error:[/bold red] Rate limit or Timeout. Retrying ({attempt + 1}/{max_retries}) after {delay}s...")
                                rotator.rotate_key()
                                await asyncio.sleep(delay)
                                delay *= 2
                            else:
                                console.print(f"[bold red]Max retries reached for {rotator.service_name}.[/bold red]")
                                raise
                        else:
                            raise
            return async_wrapper
    return decorator
