"""Timeouts, exponential backoff retries, and pipeline step logging."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def log_pipeline_step(step: str, status: str, detail: str = "") -> None:
    """Structured breadcrumb for /api/search lifecycle (trace_id comes from logging_setup)."""
    logger.info(
        "pipeline_step",
        extra={"pipeline_step": step, "pipeline_status": status, "detail": (detail or "")[:400]},
    )


async def with_timeout(coro: Awaitable[T], *, seconds: float, step: str) -> T:
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("pipeline_timeout", extra={"step": step, "seconds": seconds})
        raise


async def async_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base_delay: float,
    max_delay: float,
    step: str,
) -> T:
    last: BaseException | None = None
    for i in range(max(1, attempts)):
        try:
            return await factory()
        except Exception as e:
            last = e
            if i >= attempts - 1:
                break
            delay = min(max_delay, base_delay * (2**i))
            logger.warning(
                "pipeline_retry",
                extra={
                    "step": step,
                    "attempt": i + 1,
                    "delay_s": round(delay, 3),
                    "error": str(e)[:200],
                },
            )
            await asyncio.sleep(delay)
    assert last is not None
    raise last
