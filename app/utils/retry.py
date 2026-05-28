import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

def async_retry(max_retries: int = 3, initial_delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry async functions with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Operation failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    delay *= backoff
        return wrapper
    return decorator