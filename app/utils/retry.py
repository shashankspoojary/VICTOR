import asyncio
import functools
import logging
from typing import Callable, Any, Optional
from .key_rotation import KeyManager

logger = logging.getLogger(__name__)

def is_transient_error(e: Exception) -> bool:
    """Determine if an exception represents a transient error that should be retried."""
    err_str = str(e).lower()
    # Simple heuristic to identify typical transient network / rate-limit / server errors
    transient_indicators = [
        "429", "rate limit", "too many requests",
        "500", "502", "503", "504", "server error", "timeout",
        "connection reset", "network", "transient"
    ]
    return any(indicator in err_str for indicator in transient_indicators)

def async_retry(
    retries: int = 3, 
    initial_delay: float = 1.0, 
    backoff_factor: float = 2.0,
    key_manager: Optional[KeyManager] = None
):
    """
    An asynchronous decorator that retries a function on transient errors.
    
    Args:
        retries: Maximum number of retries before giving up.
        initial_delay: Initial delay in seconds before the first retry.
        backoff_factor: Multiplier for the delay on subsequent retries.
        key_manager: Optional KeyManager instance to rotate on failure.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if not is_transient_error(e):
                        logger.error(f"Non-transient error in {func.__name__}: {e}. Not retrying.")
                        raise e
                    
                    if attempt < retries:
                        logger.warning(
                            f"Transient error in {func.__name__} (Attempt {attempt + 1}/{retries + 1}): {e}. "
                            f"Retrying in {delay} seconds..."
                        )
                        
                        # Rotate key if a key manager was provided
                        if key_manager:
                            logger.info(f"Triggering key rotation for {key_manager.name} due to transient error.")
                            key_manager.rotate_key()
                            
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {retries} retries exhausted for {func.__name__}.")
            
            # If we exhausted all retries, raise the last encountered exception
            raise last_exception
        return wrapper
    return decorator
