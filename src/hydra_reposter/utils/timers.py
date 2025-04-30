import random
import asyncio


def backoff(wait: int | float) -> float:
    """
    Возвращает `wait + jitter`, где jitter ∈ [0;3)сек.
    """
    jitter = random.uniform(0, 3)
    return wait + jitter


async def sleep_with_backoff(wait: int | float):
    """Асинхронный `await asyncio.sleep` с джиттером."""
    await asyncio.sleep(backoff(wait))