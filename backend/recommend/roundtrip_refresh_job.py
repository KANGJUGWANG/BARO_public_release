from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from core.config import settings

log = logging.getLogger(__name__)

ROUNDTRIP_REFRESH_ENABLED = (
    os.getenv("ROUNDTRIP_REFRESH_ENABLED", "false").lower() == "true"
)

JOB_TTL_MINUTES = 60
RECENT_SUCCESS_TTL_MINUTES = 30
MAX_REFRESH_JOBS = 50

TIMEOUT_DEFAULT = 150
TIMEOUT_MIN = 60
TIMEOUT_MAX = settings.roundtrip_refresh_max_timeout_s

ROUNDTRIP_MAX_CONCURRENT = int(
    os.getenv("ROUNDTRIP_REFRESH_MAX_CONCURRENT", os.getenv("ROUNDTRIP_MAX_CONCURRENT", "4"))
)
GLOBAL_SEARCH_MAX_CONCURRENT = int(os.getenv("GLOBAL_SEARCH_MAX_CONCURRENT", "8"))


class RefreshJobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    TIMEOUT_WITH_PARTIAL = "timeout_with_partial"
    NO_RESULT = "no_result"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    ROUTE_NOT_ALLOWED = "route_not_allowed"
    LANE_BUSY = "lane_busy"
    GLOBAL_BUSY = "global_busy"
    BUSY_SCHEDULED_CRAWLER = "busy_scheduled_crawler"


@dataclass
class RefreshJobData:
    job_id: str
    cache_key: str
    origin: str
    destination: str
    depart_date: str
    return_date: str
    stay_nights: int
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
class RefreshJobStart:
    job: RefreshJobData
    response_status: str
    start_worker: bool


_active_jobs: dict[str, str] = {}
_refresh_jobs: dict[str, RefreshJobData] = {}
_recent_success: dict[str, tuple[str, datetime]] = {}
_roundtrip_sem = asyncio.Semaphore(ROUNDTRIP_MAX_CONCURRENT)
_global_search_sem = asyncio.Semaphore(GLOBAL_SEARCH_MAX_CONCURRENT)


def build_refresh_cache_key(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    stay_nights: int,
) -> str:
    return (
        f"roundtrip:{origin.upper()}:{destination.upper()}:"
        f"{depart_date}:{return_date}:{stay_nights}"
    )


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


def create_refresh_job(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    stay_nights: int,
    force_refresh: bool = False,
    timeout_seconds: int = TIMEOUT_DEFAULT,
) -> RefreshJobStart:
    _cleanup_expired()

    normalized_origin = origin.upper()
    normalized_destination = destination.upper()
    cache_key = build_refresh_cache_key(
        normalized_origin,
        normalized_destination,
        depart_date,
        return_date,
        stay_nights,
    )

    if settings.user_refresh_blocked:
        job_id = str(uuid.uuid4())
        job = RefreshJobData(
            job_id=job_id,
            cache_key=cache_key,
            origin=normalized_origin,
            destination=normalized_destination,
            depart_date=depart_date,
            return_date=return_date,
            stay_nights=stay_nights,
            force_refresh=force_refresh,
            timeout_seconds=clamp_timeout(timeout_seconds),
            fallback_available=True,
            message="서버 데이터 업데이트 중입니다. 최신 관측 결과를 표시합니다.",
        )
        _refresh_jobs[job_id] = job
        _finish_job(
            job,
            RefreshJobStatus.BUSY_SCHEDULED_CRAWLER,
            reason="user refresh blocked by server data update",
            error_code=RefreshJobStatus.BUSY_SCHEDULED_CRAWLER,
        )
        log.info("roundtrip refresh blocked: cache_key=%s job_id=%s", cache_key, job_id)
        return RefreshJobStart(
            job=job,
            response_status=RefreshJobStatus.BUSY_SCHEDULED_CRAWLER,
            start_worker=False,
        )

    existing_job_id = _active_jobs.get(cache_key)
    if existing_job_id:
        existing = _refresh_jobs.get(existing_job_id)
        if existing and existing.status in (RefreshJobStatus.QUEUED, RefreshJobStatus.RUNNING):
            log.info("roundtrip refresh duplicate_running: cache_key=%s", cache_key)
            existing.message = "duplicate_running"
            return RefreshJobStart(
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
                return RefreshJobStart(
                    job=recent_job,
                    response_status="recent_success",
                    start_worker=False,
                )

    if len(_refresh_jobs) >= MAX_REFRESH_JOBS:
        _cleanup_expired()
        if len(_refresh_jobs) >= MAX_REFRESH_JOBS:
            raise RuntimeError("max_refresh_jobs exceeded")

    job_id = str(uuid.uuid4())
    job = RefreshJobData(
        job_id=job_id,
        cache_key=cache_key,
        origin=normalized_origin,
        destination=normalized_destination,
        depart_date=depart_date,
        return_date=return_date,
        stay_nights=stay_nights,
        force_refresh=force_refresh,
        timeout_seconds=clamp_timeout(timeout_seconds),
    )
    _refresh_jobs[job_id] = job
    _active_jobs[cache_key] = job_id
    log.info(
        "roundtrip refresh job created: job_id=%s cache_key=%s enabled=%s",
        job_id,
        cache_key,
        ROUNDTRIP_REFRESH_ENABLED,
    )
    return RefreshJobStart(job=job, response_status=RefreshJobStatus.QUEUED, start_worker=True)


def get_refresh_job(job_id: str) -> RefreshJobData | None:
    _cleanup_expired()
    return _refresh_jobs.get(job_id)


def _finish_job(
    job: RefreshJobData,
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
    ):
        _recent_success[job.cache_key] = (job.job_id, datetime.now())

    if _active_jobs.get(job.cache_key) == job.job_id:
        _active_jobs.pop(job.cache_key, None)

    log.info(
        "roundtrip refresh job finished: job_id=%s status=%s elapsed=%.2f",
        job.job_id,
        status,
        job.elapsed_seconds or 0,
    )


async def _get_latest_observed_at(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    stay_nights: int,
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
                    WHERE s.route_type = 'roundtrip'
                      AND s.origin_iata = %s
                      AND s.destination_iata = %s
                      AND s.departure_date = %s
                      AND s.return_date = %s
                      AND s.stay_nights = %s
                      AND s.crawl_status = 'success'
                    """,
                    (origin, destination, depart_date, return_date, stay_nights),
                )
                row = await cur.fetchone()
                if row and row[0]:
                    return str(row[0])
    except Exception as exc:  # noqa: BLE001 - job status should be fail-soft.
        log.warning("roundtrip latest observed_at failed: %s", exc.__class__.__name__)
    return None


async def _count_candidates(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    stay_nights: int,
    pool: Any,
) -> int:
    if pool is None:
        return 0

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT MAX(s.observed_at)
                    FROM search_observation s
                    WHERE s.route_type = 'roundtrip'
                      AND s.origin_iata = %s
                      AND s.destination_iata = %s
                      AND s.departure_date = %s
                      AND s.return_date = %s
                      AND s.stay_nights = %s
                      AND s.crawl_status = 'success'
                    """,
                    (origin, destination, depart_date, return_date, stay_nights),
                )
                row = await cur.fetchone()
                if not row or not row[0]:
                    return 0
                latest = row[0]

                await cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM flight_offer_observation f
                    JOIN search_observation s ON f.observation_id = s.observation_id
                    WHERE s.route_type = 'roundtrip'
                      AND s.origin_iata = %s
                      AND s.destination_iata = %s
                      AND s.departure_date = %s
                      AND s.return_date = %s
                      AND s.stay_nights = %s
                      AND s.observed_at = %s
                      AND f.price_krw IS NOT NULL
                      AND f.flight_number IS NOT NULL
                      AND f.ret_flight_number IS NOT NULL
                      AND f.price_status = 'official_price'
                    """,
                    (origin, destination, depart_date, return_date, stay_nights, latest),
                )
                count_row = await cur.fetchone()
                return int(count_row[0]) if count_row else 0
    except Exception as exc:  # noqa: BLE001 - job status should be fail-soft.
        log.warning("roundtrip candidate count failed: %s", exc.__class__.__name__)
    return 0


async def run_refresh_job(job_id: str, pool: Any, writer_pool: Any = None) -> None:
    job = _refresh_jobs.get(job_id)
    if not job:
        return

    acquired_roundtrip = False
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
        await asyncio.wait_for(_roundtrip_sem.acquire(), timeout=5)
        acquired_roundtrip = True
    except asyncio.TimeoutError:
        if acquired_global:
            _global_search_sem.release()
            acquired_global = False
        _finish_job(
            job,
            RefreshJobStatus.LANE_BUSY,
            reason="roundtrip refresh lane concurrency limit reached",
            error_code=RefreshJobStatus.LANE_BUSY,
        )
        return

    try:
        job.status = RefreshJobStatus.RUNNING
        job.latest_observed_at_before = await _get_latest_observed_at(
            job.origin,
            job.destination,
            job.depart_date,
            job.return_date,
            job.stay_nights,
            pool,
        )
        job.candidates_available = await _count_candidates(
            job.origin,
            job.destination,
            job.depart_date,
            job.return_date,
            job.stay_nights,
            pool,
        )
        job.fallback_available = job.candidates_available > 0

        from recommend.roundtrip_refresh_executor import execute_roundtrip_refresh

        result = await execute_roundtrip_refresh(
            origin=job.origin,
            destination=job.destination,
            depart_date=job.depart_date,
            return_date=job.return_date,
            timeout_seconds=job.timeout_seconds,
            pool=pool,
            writer_pool=writer_pool,
            job_id=job.job_id,
        )
        job.latest_observed_at_after = await _get_latest_observed_at(
            job.origin,
            job.destination,
            job.depart_date,
            job.return_date,
            job.stay_nights,
            pool,
        )
        job.candidates_available = await _count_candidates(
            job.origin,
            job.destination,
            job.depart_date,
            job.return_date,
            job.stay_nights,
            pool,
        )
        job.fallback_available = job.candidates_available > 0
        inserted_count = int(result.get("inserted_count") or 0)
        job.refreshed = (
            inserted_count > 0
            or (
                job.latest_observed_at_after is not None
                and job.latest_observed_at_after != job.latest_observed_at_before
            )
        )
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
            )
            else status
        )
        _finish_job(
            job,
            status,
            reason=reason,
            error_code=error_code,
        )
    finally:
        if acquired_roundtrip:
            _roundtrip_sem.release()
        if acquired_global:
            _global_search_sem.release()
