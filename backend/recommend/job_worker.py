from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from recommend.job_store import (
    JobPredictionItem,
    JobStatus,
    _work_queue,
    cleanup_expired,
    get_job,
    requeue_job,
)

log = logging.getLogger(__name__)

_bg_sem = asyncio.Semaphore(1)


async def process_one_offer(job_id: str) -> None:
    from core.db import get_pool
    from flights.schema import SearchRequest
    from ml_inference.model_runtime import load_oneway_artifacts
    from recommend.schema import PredictOneRequest
    from recommend.service import _predict_offer, _predict_roundtrip_offer, _prediction

    job = get_job(job_id)
    if not job or not job.has_remaining:
        return

    index = job.next_offer_index
    if index >= len(job.offers):
        job.status = JobStatus.DONE
        job.updated_at = datetime.now()
        return

    offer = job.offers[index]
    job.next_offer_index += 1
    job.status = JobStatus.RUNNING
    job.updated_at = datetime.now()

    log.info(
        "bg worker: job_id=%s offer_index=%d flight_number=%s",
        job_id,
        index,
        offer.flight_number,
    )

    acquired = False
    try:
        await asyncio.wait_for(_bg_sem.acquire(), timeout=5.0)
        acquired = True

        trip_type = (job.trip_type or "oneway").lower().strip()
        if trip_type == "roundtrip":
            result = await asyncio.wait_for(
                _predict_roundtrip_offer(
                    request=PredictOneRequest(
                        origin=job.origin,
                        destination=job.destination,
                        depart_date=job.depart_date,
                        trip_type="roundtrip",
                        offer=offer.raw,
                    ),
                    pool=get_pool(),
                    runtime_ref={"runtime": None},
                ),
                timeout=90,
            )
        else:
            search_request = SearchRequest(
                origin=job.origin,
                destination=job.destination,
                depart_date=job.depart_date,
                trip_type=job.trip_type,
            )
            result = await asyncio.wait_for(
                _predict_offer(
                    offer=offer.raw,
                    request=search_request,
                    pool=get_pool(),
                    artifacts=load_oneway_artifacts(),
                    runtime_ref={"runtime": None},
                    index=index,
                ),
                timeout=90,
            )
    except asyncio.TimeoutError:
        result = _prediction(
            "unavailable_bg_timeout",
            reason="background analysis timeout",
        )
    except Exception as exc:  # noqa: BLE001 - job must continue with next offers.
        log.warning(
            "bg worker offer error: job_id=%s index=%d err=%s",
            job_id,
            index,
            exc.__class__.__name__,
        )
        result = _prediction("error", reason=exc.__class__.__name__)
    finally:
        if acquired:
            _bg_sem.release()

    _record_result(job_id, index, offer, _prediction_to_dict(result))
    requeue_job(job_id)


def _record_result(
    job_id: str,
    index: int,
    offer: Any,
    prediction: dict[str, Any],
) -> None:
    job = get_job(job_id)
    if not job:
        return

    status = prediction.get("prediction_status")
    if status == "ok":
        job.completed_count += 1
    else:
        job.failed_count += 1
        job.errors.append(
            {
                "index": index,
                "offer_observation_id": offer.offer_observation_id,
                "refresh_offer_id": offer.refresh_offer_id,
                "source_offer_id": offer.source_offer_id,
                "flight_number": offer.flight_number,
                "ret_flight_number": offer.ret_flight_number,
                "prediction_status": status,
                "reason": prediction.get("reason"),
            }
        )

    job.predictions.append(
        JobPredictionItem(
            offer_observation_id=offer.offer_observation_id,
            refresh_offer_id=offer.refresh_offer_id,
            source_offer_id=offer.source_offer_id,
            flight_number=offer.flight_number,
            dep_time=offer.dep_time,
            dep_time_local=offer.dep_time_local,
            ret_flight_number=offer.ret_flight_number,
            ret_dep_time_local=offer.ret_dep_time_local,
            return_date=offer.return_date,
            stay_nights=offer.stay_nights,
            price_krw=offer.price_krw,
            prediction=prediction,
        )
    )

    if job.cancelled:
        job.status = JobStatus.CANCELLED
    elif job.is_complete:
        job.status = JobStatus.DONE
    elif job.completed_count + job.failed_count > 0:
        job.status = JobStatus.PARTIAL
    else:
        job.status = JobStatus.RUNNING
    job.updated_at = datetime.now()


def _prediction_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return dict(result)


async def background_worker_loop() -> None:
    log.info("background worker started")
    while True:
        try:
            job_id = await asyncio.wait_for(_work_queue.get(), timeout=2.0)
            try:
                job = get_job(job_id)
                if job and job.has_remaining:
                    await process_one_offer(job_id)
            finally:
                _work_queue.task_done()

            await asyncio.sleep(0)
            cleanup_expired()
        except asyncio.TimeoutError:
            cleanup_expired()
        except asyncio.CancelledError:
            log.info("background worker cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - keep worker alive.
            log.error("background worker error: %s", exc.__class__.__name__)
            await asyncio.sleep(1)
