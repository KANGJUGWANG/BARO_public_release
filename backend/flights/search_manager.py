from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


try:
    from core.config import settings

    CRAWLER_MAX_CONCURRENCY = int(
        getattr(settings, "crawler_max_concurrency", None)
        or _env_int("CRAWLER_MAX_CONCURRENCY", 4)
    )
    CACHE_TTL_SEC = int(
        getattr(settings, "flight_search_cache_ttl_sec", None)
        or _env_int("FLIGHT_SEARCH_CACHE_TTL_SEC", 300)
    )
    WAIT_TIMEOUT_SEC = int(
        getattr(settings, "flight_search_wait_timeout_sec", None)
        or _env_int("FLIGHT_SEARCH_WAIT_TIMEOUT_SEC", 25)
    )
except Exception:
    CRAWLER_MAX_CONCURRENCY = _env_int("CRAWLER_MAX_CONCURRENCY", 4)
    CACHE_TTL_SEC = _env_int("FLIGHT_SEARCH_CACHE_TTL_SEC", 300)
    WAIT_TIMEOUT_SEC = _env_int("FLIGHT_SEARCH_WAIT_TIMEOUT_SEC", 25)

MAX_CACHE_SIZE = 100


@dataclass
class _CacheEntry:
    result: Any
    saved_at: float


@dataclass
class SearchOutcome:
    result: Any | None = None
    retryable_busy: bool = False
    failed: bool = False


_cache: dict[str, _CacheEntry] = {}
_inflight: dict[str, asyncio.Future[SearchOutcome]] = {}
_lock = asyncio.Lock()
_sem = asyncio.Semaphore(CRAWLER_MAX_CONCURRENCY)


def build_search_key(
    origin: str,
    destination: str,
    depart_date: str,
    trip_type: str,
    return_date: str | None = None,
) -> str:
    parts = [
        str(trip_type or "").lower().strip(),
        str(origin or "").upper().strip(),
        str(destination or "").upper().strip(),
        str(depart_date or "").strip(),
    ]
    if return_date:
        parts.append(str(return_date).strip())
    return "_".join(parts)


def _is_valid(entry: _CacheEntry) -> bool:
    return time.monotonic() - entry.saved_at < CACHE_TTL_SEC


def _cleanup_cache() -> None:
    now = time.monotonic()
    expired = [key for key, value in _cache.items() if now - value.saved_at >= CACHE_TTL_SEC]
    for key in expired:
        del _cache[key]

    if len(_cache) <= MAX_CACHE_SIZE:
        return

    oldest_keys = sorted(_cache.keys(), key=lambda key: _cache[key].saved_at)
    for key in oldest_keys[: len(_cache) - MAX_CACHE_SIZE]:
        del _cache[key]


async def _run_crawler(
    search_key: str,
    future: asyncio.Future[SearchOutcome],
    crawler_fn: Callable[[], Awaitable[Any]],
) -> None:
    acquired = False
    try:
        await asyncio.wait_for(_sem.acquire(), timeout=WAIT_TIMEOUT_SEC)
        acquired = True
    except asyncio.TimeoutError:
        log.warning("search semaphore wait timeout: key=%s", search_key)
        if not future.done():
            future.set_result(SearchOutcome(retryable_busy=True))
        async with _lock:
            _inflight.pop(search_key, None)
        return

    try:
        result = await crawler_fn()
        if result is not None:
            async with _lock:
                _cache[search_key] = _CacheEntry(result=result, saved_at=time.monotonic())
        if not future.done():
            future.set_result(SearchOutcome(result=result))
    except asyncio.CancelledError:
        if not future.done():
            future.set_result(SearchOutcome(failed=True))
        raise
    except Exception as exc:
        log.warning("search crawler error: key=%s err=%s", search_key, exc)
        if not future.done():
            future.set_result(SearchOutcome(failed=True))
    finally:
        if acquired:
            _sem.release()
        async with _lock:
            _inflight.pop(search_key, None)
            _cleanup_cache()


async def search_managed(search_key: str, crawler_fn: Callable[[], Awaitable[Any]]) -> tuple[Any | None, bool]:
    """
    Return (result, retryable_busy).
    The crawler task is decoupled from an individual caller so client aborts do
    not cancel the shared in-flight result for the same search key.
    """
    async with _lock:
        _cleanup_cache()
        entry = _cache.get(search_key)
        if entry and _is_valid(entry):
            log.info("search cache hit: key=%s", search_key)
            return entry.result, False

        future = _inflight.get(search_key)
        if future is None:
            future = asyncio.get_running_loop().create_future()
            _inflight[search_key] = future
            asyncio.create_task(_run_crawler(search_key, future, crawler_fn))
            log.info("search started: key=%s", search_key)
        else:
            log.info("search coalescing: key=%s", search_key)

    try:
        outcome = await asyncio.wait_for(
            asyncio.shield(future),
            timeout=WAIT_TIMEOUT_SEC + 30,
        )
    except asyncio.TimeoutError:
        log.warning("search wait timeout: key=%s", search_key)
        return None, True

    if outcome.retryable_busy:
        return None, True
    if outcome.failed:
        return None, False
    return outcome.result, False
