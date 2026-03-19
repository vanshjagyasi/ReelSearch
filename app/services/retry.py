"""Simple async retry decorator with exponential backoff."""

import asyncio
import functools
import logging

logger = logging.getLogger(__name__)


def async_retry(max_attempts: int = 3, base_delay: float = 1.0):
    """Retry an async function with exponential backoff.

    Delays: base_delay, base_delay*2, base_delay*4, ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                        func.__name__, attempt, max_attempts, delay, exc,
                    )
                    await asyncio.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
