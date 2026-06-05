from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from core.config import settings
from recommend.oneway_refresh_executor import build_oneway_route_key, is_route_allowed
from recommend.roundtrip_refresh_job import RefreshJobStatus, _global_search_sem

log = logging.getLogger(__name__)

JOB_TTL_MINUTES = 60
RECENT_SUCCESS_TTL_MINUTES = 30
MAX_REFRESH_JOBS = 50

TIMEOUT_DEFAULT = 150
TIMEOUT_MIN = 30
TIMEOUT_MAX = settings.oneway_refresh_max_timeout_s

ONEWAY_MAX_CONCURRENT = int(
    os.getenv("ONEWAY_REFRESH_MAX_CONCURRENT", os.getenv("ONEWAY_MAX_CONCURRENT", "4"))
)
SKIPPED_FRESH_REALTIME = "skipped_fresh_realtime"


@dataclass
class OnewayRefreshJobData:
    job_id: str
    cache_key: str
    origin: str
    destination: str
    depart_date: str
    force_refresh: bool
    timeout_seconds: int
    status: str = RefreshJobStatus.QUEUED
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    latest_observed_at_before: str | None = None
    latest_observed_at_after: str | None = None
    refreshed: bool = False
    candidates_available: int = 0
    fallback_available: bool = False
    error_code: str | None = None
    reason: str | None = None
    message: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(minutes=JOB_TTL_MINUTES)
    )


@dataclass
class OnewayRefreshJobStart:
    job: OnewayRefreshJobData
    response_status: str
    start_worker: bool


_active_jobs: dict[str, str] = {}
_refresh_jobs: dict[str, OnewayRefreshJobData] = {}
_recent_success: dict[str, tuple[str, datetime]] = {}
_oneway_sem = asyncio.Semaphore(ONEWAY_MAX_CONCURRENT)


def _cleanup_expired() -> None:
    now = datetime.now()
    expired_jobs = [job_id for job_id, job in _refresh_jobs.items() if job.expires_at < now]
    for job_id in expired_jobs:
        job = _refresh_jobs.pop(job_id, None)
        if job and _active_jobs.get(job.cache_key) == job_id:
            _active_jobs.pop(job.cache_key, None)

    expired_success = [
        key
        for key, (_, saved_at) in _recent_success.items()
        if saved_at + timedelta(minutes=RECENT_SUCCESS_TTL_MINUTES) < now
    ]
    for key in expired_success:
        _recent_success.pop(key, None)


def clamp_timeout(seconds: int | None) -> int:
    value = seconds if isinstance(seconds, int) else TIMEOUT_DEFAULT
    return max(TIMEOUT_MIN, min(TIMEOUT_MAX, value))


def _terminal_job(
    *,
    cache_key: str,
    origin: str,
    destination: str,
    depart_date: str,
    force_refresh: bool,
    timeout_seconds: int,
    status: str,
    reason: str,
    error_code: str | None = None,
    message: str | None = None,
) -> OnewayRefreshJobStart:
    job_id = str(uuid.uuid4())
    job = OnewayRefreshJobData(
        job_id=job_id,
        cache_key=cache_key,
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        force_refresh=force_refresh,
        timeout_seconds=clamp_timeout(timeout_seconds),
        fallback_available=True,
        message=message,
    )
    _refresh_jobs[job_id] = job
    _finish_job(job, status, reason=reason, error_code=error_code or status)
    return OnewayRefreshJobStart(job=job, response_status=status, start_worker=False)


def create_oneway_refresh_job(
    origin: str,
    destination: str,
    depart_date: str,
    force_refresh: bool = False,
    timeout_seconds: int = TIMEOUT_DEFAULT,
) -> OnewayRefreshJobStart:
    _cleanup_expired()

    normalized_origin = origin.upper()
    normalized_destination = destination.upper()
    normalized_depart_date = depart_date.strip()
    cache_key = build_oneway_route_key(
        normalized_origin,
        normalized_destination,
        normalized_depart_date,
    )

    if settings.user_refresh_blocked:
        log.info("oneway refresh blocked: cache_key=%s", cache_key)
        return _terminal_job(
            cache_key=cache_key,
            origin=normalized_origin,
            destination=normalized_destination,
            depart_date=normalized_depart_date,
            force_refresh=force_refresh,
            timeout_seconds=timeout_seconds,
            status=RefreshJobStatus.BUSY_SCHEDULED_CRAWLER,
            reason="user refresh blocked by server data update",
            message="server data update in progress; using latest observed candidates",
        )

    if not settings.oneway_refresh_enabled or settings.oneway_refresh_mode.strip().lower() == "disabled":
        return _terminal_job(
            cache_key=cache_key,
            origin=normalized_origin,
            destination=normalized_destination,
            depart_date=normalized_depart_date,
            force_refresh=force_refresh,
            timeout_seconds=timeout_seconds,
            status=RefreshJobStatus.DISABLED,
            reason="oneway refresh execution is disabled",
            message="latest observed candidates remain available",
        )

    if not is_route_allowed(normalized_origin, normalized_destination):
        return _terminal_job(
            cache_key=cache_key,
            origin=normalized_origin,
            destination=normalized_destination,
            depart_date=normalized_depart_date,
            force_refresh=force_refresh,
            timeout_seconds=timeout_seconds,
            status=RefreshJobStatus.ROUTE_NOT_ALLOWED,
            reason=f"route {normalized_origin}-{normalized_destination} is not in allowlist",
            message="route is not eligible for realtime refresh",
        )

    existing_job_id = _active_jobs.get(cache_key)
    if existing_job_id:
        existing = _refresh_jobs.get(existing_job_id)
        if existing and existing.status in (RefreshJobStatus.QUEUED, RefreshJobStatus.RUNNING):
            log.info("oneway refresh duplicate_running: cache_key=%s", cache_key)
            existing.message = "duplicate_running"
            return OnewayRefreshJobStart(
                job=existing,
                response_status="duplicate_running",
                start_worker=False,
            )

    if not force_refresh:
        recent = _recent_success.get(cache_key)
        if recent:
            recent_job_id, _ = recent
            recent_job = _refresh_jobs.get(recent_job_id)
            if recent_job:
                recent_job.message = "recent_success"
                return OnewayRefreshJobStart(
                    job=recent_job,
                    response_status="recent_success",
                    start_worker=False,
                )

    if len(_refresh_jobs) >= MAX_REFRESH_JOBS:
        _cleanup_expired()
        if len(_refresh_jobs) >= MAX_REFRESH_JOBS:
            raise RuntimeError("max_oneway_refresh_jobs exceeded")

    job_id = str(uuid.uuid4())
    job = OnewayRefreshJobData(
        job_id=job_id,
        cache_key=cache_key,
        origin=normalized_origin,
        destination=normalized_destination,
        depart_date=normalized_depart_date,
        force_refresh=force_refresh,
        timeout_seconds=clamp_timeout(timeout_seconds),
    )
    _refresh_jobs[job_id] = job
    _active_jobs[cache_key] = job_id
    log.info("oneway refresh job created: job_id=%s cache_key=%s", job_id, cache_key)
    return OnewayRefreshJobStart(job=job, response_status=RefreshJobStatus.QUEUED, start_worker=True)


def get_oneway_refresh_job(job_id: str) -> OnewayRefreshJobData | None:
    _cleanup_expired()
    return _refresh_jobs.get(job_id)


def _finish_job(
    job: OnewayRefreshJobData,
    status: str,
    reason: str | None = None,
    error_code: str | None = None,
) -> None:
    job.status = status
    job.finished_at = datetime.now().isoformat(timespec="seconds")
    started = datetime.fromisoformat(job.started_at)
    job.elapsed_seconds = round((datetime.now() - started).total_seconds(), 2)
    job.reason = reason
    job.error_code = error_code

    if status in (
        RefreshJobStatus.SUCCESS,
        RefreshJobStatus.PARTIAL_SUCCESS,
        RefreshJobStatus.TIMEOUT_WITH_PARTIAL,
        SKIPPED_FRESH_REALTIME,
    ):
        _recent_success[job.cache_key] = (job.job_id, datetime.now())

    if _active_jobs.get(job.cache_key) == job.job_id:
        _active_jobs.pop(job.cache_key, None)

    log.info(
        "oneway refresh job finished: job_id=%s status=%s elapsed=%.2f",
        job.job_id,
        status,
        job.elapsed_seconds or 0,
    )


async def _get_latest_observed_at(
    origin: str,
    destination: str,
    depart_date: str,
    pool: Any,
) -> str | None:
    if pool is None:
        return None

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT MAX(s.observed_at)
                    FROM search_observation s
                    WHERE s.route_type = 'oneway'
                      AND s.origin_iata = %s
                      AND s.destination_iata = %s
                      AND s.departure_date = %s
                      AND s.crawl_status = 'success'
                    """,
                    (origin, destination, depart_date),
                )
                row = await cur.fetchone()
                if row and row[0]:
                    return str(row[0])
    except Exception as exc:  # noqa: BLE001 - job status should be fail-soft.
        log.warning("oneway latest observed_at failed: %s", exc.__class__.__name__)
    return None


async def _count_candidates(
    origin: str,
    destination: str,
    depart_date: str,
    pool: Any,
) -> int:
    if pool is None:
        return 0

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT s.observed_at
                    FROM search_observation s
                    JOIN flight_offer_observation f ON f.observation_id = s.observation_id
                    WHERE s.route_type = 'oneway'
                      AND s.origin_iata = %s
                      AND s.destination_iata = %s
                      AND s.departure_date = %s
                      AND s.crawl_status = 'success'
                      AND f.price_krw IS NOT NULL
                      AND f.flight_number IS NOT NULL
                      AND f.price_status = 'official_price'
                    GROUP BY s.observation_id, s.observed_at
                    ORDER BY s.observed_at DESC, s.observation_id DESC
                    LIMIT 1
                    """,
                    (origin, destination, depart_date),
                )
                row = await cur.fetchone()
                if not row or not row[0]:
                    return 0
                observed_at = row[0]

                await cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM flight_offer_observation f
                    JOIN search_observation s ON f.observation_id = s.observation_id
                    WHERE s.route_type = 'oneway'
                      AND s.origin_iata = %s
                      AND s.destination_iata = %s
                      AND s.departure_date = %s
                      AND s.observed_at = %s
                      AND s.crawl_status = 'success'
                      AND f.price_krw IS NOT NULL
                      AND f.flight_number IS NOT NULL
                      AND f.price_status = 'official_price'
                    """,
                    (origin, destination, depart_date, observed_at),
                )
                count_row = await cur.fetchone()
                return int(count_row[0]) if count_row else 0
    except Exception as exc:  # noqa: BLE001 - job status should be fail-soft.
        log.warning("oneway candidate count failed: %s", exc.__class__.__name__)
    return 0


async def run_oneway_refresh_job(job_id: str, pool: Any, writer_pool: Any = None) -> None:
    job = _refresh_jobs.get(job_id)
    if not job:
        return

    acquired_oneway = False
    acquired_global = False

    try:
        await asyncio.wait_for(_global_search_sem.acquire(), timeout=5)
        acquired_global = True
    except asyncio.TimeoutError:
        _finish_job(
            job,
            RefreshJobStatus.GLOBAL_BUSY,
            reason="global refresh concurrency limit reached",
            error_code=RefreshJobStatus.GLOBAL_BUSY,
        )
        return

    try:
        await asyncio.wait_for(_oneway_sem.acquire(), timeout=5)
        acquired_oneway = True
    except asyncio.TimeoutError:
        if acquired_global:
            _global_search_sem.release()
            acquired_global = False
        _finish_job(
            job,
            RefreshJobStatus.LANE_BUSY,
            reason="oneway refresh lane concurrency limit reached",
            error_code=RefreshJobStatus.LANE_BUSY,
        )
        return

    try:
        job.status = RefreshJobStatus.RUNNING
        job.latest_observed_at_before = await _get_latest_observed_at(
            job.origin,
            job.destination,
            job.depart_date,
            pool,
        )
        job.candidates_available = await _count_candidates(
            job.origin,
            job.destination,
            job.depart_date,
            pool,
        )
        job.fallback_available = job.candidates_available > 0

        from recommend.oneway_refresh_executor import execute_oneway_refresh

        result = await execute_oneway_refresh(
            origin=job.origin,
            destination=job.destination,
            depart_date=job.depart_date,
            timeout_seconds=job.timeout_seconds,
            pool=pool,
            writer_pool=writer_pool,
            job_id=job.job_id,
            force_refresh=job.force_refresh,
        )
        job.latest_observed_at_after = await _get_latest_observed_at(
            job.origin,
            job.destination,
            job.depart_date,
            pool,
        )
        job.candidates_available = await _count_candidates(
            job.origin,
            job.destination,
            job.depart_date,
            pool,
        )
        job.fallback_available = job.candidates_available > 0

        inserted_count = int(result.get("inserted_count") or 0)
        job.refreshed = inserted_count > 0
        status = str(result.get("status") or RefreshJobStatus.FAILED)
        reason = result.get("error")
        message = result.get("message")
        if message:
            job.message = str(message)
        error_code = (
            None
            if status
            in (
                RefreshJobStatus.SUCCESS,
                RefreshJobStatus.PARTIAL_SUCCESS,
                RefreshJobStatus.TIMEOUT_WITH_PARTIAL,
                RefreshJobStatus.NO_RESULT,
                SKIPPED_FRESH_REALTIME,
            )
            else status
        )
        _finish_job(job, status, reason=reason, error_code=error_code)
    finally:
        if acquired_oneway:
            _oneway_sem.release()
        if acquired_global:
            _global_search_sem.release()
