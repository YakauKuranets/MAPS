"""CockroachDB utility functions — retry logic for serialization conflicts.

CockroachDB uses optimistic concurrency control; SQLSTATE 40001 errors
are expected under contention and should be retried with backoff + jitter.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CockroachRetryExhausted(Exception):
    """All retry attempts for a CockroachDB transaction have been exhausted."""


def _is_serialization_failure(exc: Exception) -> bool:
    """Detect CockroachDB serialization conflict (SQLSTATE 40001)."""
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate == "40001":
        return True
    txt = str(exc)
    return (
        "40001" in txt
        or "SerializationFailure" in txt
        or "serialization failure" in txt.lower()
    )


def retry_on_serialization_failure(
    max_retries: int = 3, delay: float = 0.5, jitter: float = 0.2
):
    """Retry wrapper for CockroachDB serialization conflicts (SQLSTATE 40001).

    Args:
        max_retries: Maximum number of retry attempts
        delay: Base delay between retries (multiplied by attempt number)
        jitter: Random jitter added to delay to prevent thundering herd
    """

    def decorator(func: Callable[..., Any]):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if _is_serialization_failure(e):
                            wait = delay * (attempt + 1) + random.uniform(0, jitter)
                            logger.warning(
                                (
                                    "[CockroachDB] Конфликт транзакций "
                                    "(Попытка %s/%s). Повтор через %.2fs..."
                                ),
                                attempt + 1,
                                max_retries,
                                wait,
                            )
                            await asyncio.sleep(wait)
                            continue
                        raise
                logger.error(
                    "[CockroachDB] Транзакция провалена после %d попыток.", max_retries
                )
                raise CockroachRetryExhausted(
                    f"Max retries ({max_retries}) reached for CockroachDB transaction"
                )

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if _is_serialization_failure(e):
                        wait = delay * (attempt + 1) + random.uniform(0, jitter)
                        logger.warning(
                            (
                                "[CockroachDB] Конфликт транзакций "
                                "(Попытка %s/%s). Повтор через %.2fs..."
                            ),
                            attempt + 1,
                            max_retries,
                            wait,
                        )
                        time.sleep(wait)
                        continue
                    raise
            logger.error(
                "[CockroachDB] Транзакция провалена после %d попыток.", max_retries
            )
            raise CockroachRetryExhausted(
                f"Max retries ({max_retries}) reached for CockroachDB transaction"
            )

        return sync_wrapper

    return decorator


async def cockroach_health_check(engine) -> dict:
    """Check CockroachDB cluster health via the engine.

    Args:
        engine: SQLAlchemy async engine

    Returns:
        dict with status, version, node count
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute("SELECT version()")
            version = result.scalar()
            return {"status": "healthy", "version": str(version)[:100]}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)[:200]}
