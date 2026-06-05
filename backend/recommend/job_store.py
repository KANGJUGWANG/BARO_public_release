from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

log = logging.getLogger(__name__)

JOB_TTL_MINUTES = 30
MAX_JOBS = 20
MAX_OFFERS_PER_JOB = 50


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobOffer:
    offer_observation_id: Optional[int]
    refresh_offer_id: Optional[int]
    source_offer_id: Optional[int]
    flight_number: Optional[str]
    dep_time: Optional[str]
    dep_time_local: Optional[str]
    ret_flight_number: Optional[str]
    ret_dep_time_local: Optional[str]
    return_date: Optional[str]
    stay_nights: Optional[int]
    price_krw: Optional[int]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobPredictionItem:
    offer_observation_id: Optional[int]
    refresh_offer_id: Optional[int]
    source_offer_id: Optional[int]
    flight_number: Optional[str]
    dep_time: Optional[str]
    dep_time_local: Optional[str]
    ret_flight_number: Optional[str]
    ret_dep_time_local: Optional[str]
    return_date: Optional[str]
    stay_nights: Optional[int]
    price_krw: Optional[int]
    prediction: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobData:
    job_id: str
    origin: str
    destination: str
    depart_date: str
    trip_type: str
    offers: list[JobOffer]
    status: str = JobStatus.QUEUED
    completed_count: int = 0
    failed_count: int = 0
    predictions: list[JobPredictionItem] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    cancelled: bool = False
    next_offer_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(minutes=JOB_TTL_MINUTES)
    )

    @property
    def total_count(self) -> int:
        return len(self.offers)

    @property
    def is_complete(self) -> bool:
        return self.next_offer_index >= len(self.offers)

    @property
    def has_remaining(self) -> bool:
        return not self.cancelled and not self.is_complete


_jobs: dict[str, JobData] = {}
_work_queue: asyncio.Queue[str] = asyncio.Queue()


def cleanup_expired() -> int:
    now = datetime.now()
    expired = [job_id for job_id, job in _jobs.items() if job.expires_at < now]
    for job_id in expired:
        del _jobs[job_id]
    return len(expired)


def active_job_count() -> int:
    cleanup_expired()
    return len(_jobs)


def create_job(
    origin: str,
    destination: str,
    depart_date: str,
    trip_type: str,
    offers: list[dict[str, Any]],
) -> JobData:
    cleanup_expired()

    if len(_jobs) >= MAX_JOBS:
        raise RuntimeError("max_jobs exceeded")

    job_id = str(uuid.uuid4())
    limited_offers = offers[:MAX_OFFERS_PER_JOB]
    job_offers = [
        JobOffer(
            offer_observation_id=offer.get("offer_observation_id"),
            refresh_offer_id=offer.get("refresh_offer_id"),
            source_offer_id=offer.get("source_offer_id"),
            flight_number=offer.get("flight_number"),
            dep_time=offer.get("dep_time") or offer.get("dep_time_local"),
            dep_time_local=offer.get("dep_time_local") or offer.get("dep_time"),
            ret_flight_number=offer.get("ret_flight_number"),
            ret_dep_time_local=offer.get("ret_dep_time_local"),
            return_date=offer.get("return_date"),
            stay_nights=offer.get("stay_nights"),
            price_krw=offer.get("price_krw"),
            raw=offer,
        )
        for offer in limited_offers
    ]

    job = JobData(
        job_id=job_id,
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        trip_type=trip_type,
        offers=job_offers,
    )
    if not job_offers:
        job.status = JobStatus.DONE
    _jobs[job_id] = job
    if job.has_remaining:
        _work_queue.put_nowait(job_id)
    log.info("job created: job_id=%s total_offers=%d", job_id, len(job_offers))
    return job


def get_job(job_id: str) -> Optional[JobData]:
    cleanup_expired()
    return _jobs.get(job_id)


def cancel_job(job_id: str) -> bool:
    job = _jobs.get(job_id)
    if not job:
        return False
    job.cancelled = True
    job.status = JobStatus.CANCELLED
    job.updated_at = datetime.now()
    log.info("job cancelled: job_id=%s", job_id)
    return True


def requeue_job(job_id: str) -> None:
    job = _jobs.get(job_id)
    if job and job.has_remaining:
        _work_queue.put_nowait(job_id)
