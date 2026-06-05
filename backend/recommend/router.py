from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from core.db import get_pool, get_writer_pool
from recommend.oneway_refresh_job import (
    create_oneway_refresh_job,
    get_oneway_refresh_job,
    run_oneway_refresh_job,
)
from recommend.roundtrip_refresh_job import (
    create_refresh_job,
    get_refresh_job,
    run_refresh_job,
)
from recommend.schema import (
    AnalyzeJobRequest,
    AnalyzeJobResponse,
    HistoryRequest,
    HistoryResponse,
    JobStatusResponse,
    ModelInfoResponse,
    OnewayCandidatesRequest,
    OnewayCandidatesResponse,
    OnewayRefreshJobRequest,
    OnewayRefreshJobStartResponse,
    OnewayRefreshJobStatusResponse,
    PredictOneRequest,
    PredictionResult,
    RecommendSearchRequest,
    RecommendSearchResponse,
    RouteAnalysisItem,
    RouteAnalysisResponse,
    RoundtripCandidatesRequest,
    RoundtripCandidatesResponse,
    RoundtripRefreshJobRequest,
    RoundtripRefreshJobStartResponse,
    RoundtripRefreshJobStatusResponse,
)
from recommend.route_analysis import (
    get_all_route_analysis_snapshots,
    summarize_route_analysis_status,
)
from recommend.service import (
    cancel_job_by_id,
    get_flight_history,
    get_job_status,
    get_model_info,
    get_oneway_candidates,
    get_roundtrip_candidates,
    predict_one_offer,
    recommend_search,
    submit_analyze_job,
)

router = APIRouter(tags=["recommend"])
logger = logging.getLogger(__name__)

_recommend_sem = asyncio.Semaphore(1)


def _error_response(request: RecommendSearchRequest, error: str) -> RecommendSearchResponse:
    return RecommendSearchResponse(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        offers=[],
        crawled_at=datetime.now().isoformat(timespec="seconds"),
        error=error,
    )


def _prediction_error(status: str, reason: str) -> PredictionResult:
    return PredictionResult(
        prediction_status=status,
        reason=reason,
        model_version="finaltest_clean_v1",
    )


async def _acquire_recommend_slot(timeout: float = 0.1) -> bool:
    try:
        await asyncio.wait_for(_recommend_sem.acquire(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


@router.post("/search", response_model=RecommendSearchResponse)
async def search(request: RecommendSearchRequest) -> RecommendSearchResponse:
    acquired = await _acquire_recommend_slot()
    if not acquired:
        return _error_response(request, "recommend busy")

    try:
        return await asyncio.wait_for(recommend_search(request), timeout=300)
    except asyncio.TimeoutError:
        return _error_response(request, "recommend timeout")
    except Exception:
        return _error_response(request, "recommend failed")
    finally:
        _recommend_sem.release()


@router.post("/predict-one", response_model=PredictionResult)
async def predict_one(request: PredictOneRequest) -> PredictionResult:
    acquired = await _acquire_recommend_slot()
    if not acquired:
        return _prediction_error(
            "unavailable_predict_busy",
            "another prediction is running",
        )

    try:
        return await asyncio.wait_for(predict_one_offer(request), timeout=120)
    except asyncio.TimeoutError:
        return _prediction_error(
            "unavailable_predict_timeout",
            "prediction timeout",
        )
    except Exception:
        return _prediction_error("error", "prediction failed")
    finally:
        _recommend_sem.release()


@router.post("/history", response_model=HistoryResponse)
async def flight_history(request: HistoryRequest) -> HistoryResponse:
    try:
        return await asyncio.wait_for(get_flight_history(request), timeout=30)
    except asyncio.TimeoutError:
        return HistoryResponse(status="error", reason="history query timeout")
    except Exception:
        return HistoryResponse(status="error", reason="history query failed")


@router.post("/oneway-candidates", response_model=OnewayCandidatesResponse)
async def oneway_candidates(
    request: OnewayCandidatesRequest,
) -> OnewayCandidatesResponse:
    origin = (request.origin or "").strip().upper()
    destination = (request.destination or "").strip().upper()
    depart_date = (request.depart_date or "").strip()

    try:
        return await asyncio.wait_for(get_oneway_candidates(request), timeout=15)
    except asyncio.TimeoutError:
        return OnewayCandidatesResponse(
            status="unavailable_db_query_error",
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            reason="candidates query timeout",
        )
    except Exception as exc:
        logger.warning("oneway_candidates error: %s", exc.__class__.__name__)
        return OnewayCandidatesResponse(
            status="unavailable_db_query_error",
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            reason=exc.__class__.__name__,
        )


@router.post("/roundtrip-candidates", response_model=RoundtripCandidatesResponse)
async def roundtrip_candidates(
    request: RoundtripCandidatesRequest,
) -> RoundtripCandidatesResponse:
    try:
        return await asyncio.wait_for(get_roundtrip_candidates(request), timeout=15)
    except asyncio.TimeoutError:
        return RoundtripCandidatesResponse(
            status="error",
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            return_date=request.return_date,
            stay_nights=request.stay_nights,
            reason="candidates query timeout",
        )
    except Exception as exc:
        return RoundtripCandidatesResponse(
            status="error",
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            return_date=request.return_date,
            stay_nights=request.stay_nights,
            reason=exc.__class__.__name__,
        )


@router.post(
    "/oneway-refresh-job",
    response_model=OnewayRefreshJobStartResponse,
)
async def oneway_refresh_job(
    request: OnewayRefreshJobRequest,
    background_tasks: BackgroundTasks,
) -> OnewayRefreshJobStartResponse:
    try:
        origin = request.origin.upper().strip()
        destination = request.destination.upper().strip()
        depart_date = request.depart_date.strip()
        date.fromisoformat(depart_date)

        start = create_oneway_refresh_job(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            force_refresh=request.force_refresh,
            timeout_seconds=request.timeout_seconds,
        )
        job = start.job

        if start.start_worker:
            background_tasks.add_task(run_oneway_refresh_job, job.job_id, get_pool(), get_writer_pool())

        return OnewayRefreshJobStartResponse(
            job_id=job.job_id,
            status=start.response_status,
            cache_key=job.cache_key,
            origin=job.origin,
            destination=job.destination,
            depart_date=job.depart_date,
            force_refresh=job.force_refresh,
            timeout_seconds=job.timeout_seconds,
            started_at=job.started_at,
            latest_observed_at_before=job.latest_observed_at_before,
            fallback_available=job.fallback_available,
            message=job.message,
            reason=job.reason,
        )
    except Exception as exc:  # noqa: BLE001 - endpoint should fail soft.
        logger.warning("oneway_refresh_job error: %s", exc.__class__.__name__)
        return OnewayRefreshJobStartResponse(
            job_id="error",
            status="error",
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            force_refresh=request.force_refresh,
            timeout_seconds=request.timeout_seconds,
            reason=exc.__class__.__name__,
        )


@router.get(
    "/oneway-refresh-job/{job_id}",
    response_model=OnewayRefreshJobStatusResponse,
)
async def get_oneway_refresh_job_status(
    job_id: str,
) -> OnewayRefreshJobStatusResponse:
    job = get_oneway_refresh_job(job_id)
    if not job:
        return OnewayRefreshJobStatusResponse(
            job_id=job_id,
            status="not_found",
            reason="job not found or expired",
        )

    return OnewayRefreshJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        cache_key=job.cache_key,
        origin=job.origin,
        destination=job.destination,
        depart_date=job.depart_date,
        started_at=job.started_at,
        finished_at=job.finished_at,
        elapsed_seconds=job.elapsed_seconds,
        latest_observed_at_before=job.latest_observed_at_before,
        latest_observed_at_after=job.latest_observed_at_after,
        refreshed=job.refreshed,
        candidates_available=job.candidates_available,
        fallback_available=job.fallback_available,
        error_code=job.error_code,
        reason=job.reason,
        message=job.message,
    )


@router.post(
    "/roundtrip-refresh-job",
    response_model=RoundtripRefreshJobStartResponse,
)
async def roundtrip_refresh_job(
    request: RoundtripRefreshJobRequest,
    background_tasks: BackgroundTasks,
) -> RoundtripRefreshJobStartResponse:
    try:
        origin = request.origin.upper().strip()
        destination = request.destination.upper().strip()
        depart_date = request.depart_date.strip()
        dep = date.fromisoformat(depart_date)
        return_date = (
            request.return_date.strip()
            if request.return_date
            else (dep + timedelta(days=7)).isoformat()
        )
        stay_nights = 7

        start = create_refresh_job(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            stay_nights=stay_nights,
            force_refresh=request.force_refresh,
            timeout_seconds=request.timeout_seconds,
        )
        job = start.job

        if start.start_worker:
            background_tasks.add_task(run_refresh_job, job.job_id, get_pool(), get_writer_pool())

        return RoundtripRefreshJobStartResponse(
            job_id=job.job_id,
            status=start.response_status,
            cache_key=job.cache_key,
            origin=job.origin,
            destination=job.destination,
            depart_date=job.depart_date,
            return_date=job.return_date,
            stay_nights=job.stay_nights,
            force_refresh=job.force_refresh,
            timeout_seconds=job.timeout_seconds,
            started_at=job.started_at,
            latest_observed_at_before=job.latest_observed_at_before,
            fallback_available=job.fallback_available,
            message=job.message,
        )
    except Exception as exc:  # noqa: BLE001 - endpoint should fail soft.
        logger.warning("roundtrip_refresh_job error: %s", exc.__class__.__name__)
        return RoundtripRefreshJobStartResponse(
            job_id="error",
            status="error",
            origin=request.origin,
            destination=request.destination,
            depart_date=request.depart_date,
            return_date=request.return_date,
            stay_nights=7,
            force_refresh=request.force_refresh,
            timeout_seconds=request.timeout_seconds,
            reason=exc.__class__.__name__,
        )


@router.get(
    "/roundtrip-refresh-job/{job_id}",
    response_model=RoundtripRefreshJobStatusResponse,
)
async def get_roundtrip_refresh_job_status(
    job_id: str,
) -> RoundtripRefreshJobStatusResponse:
    job = get_refresh_job(job_id)
    if not job:
        return RoundtripRefreshJobStatusResponse(
            job_id=job_id,
            status="not_found",
            reason="job not found or expired",
        )

    return RoundtripRefreshJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        cache_key=job.cache_key,
        origin=job.origin,
        destination=job.destination,
        depart_date=job.depart_date,
        return_date=job.return_date,
        stay_nights=job.stay_nights,
        started_at=job.started_at,
        finished_at=job.finished_at,
        elapsed_seconds=job.elapsed_seconds,
        latest_observed_at_before=job.latest_observed_at_before,
        latest_observed_at_after=job.latest_observed_at_after,
        refreshed=job.refreshed,
        candidates_available=job.candidates_available,
        fallback_available=job.fallback_available,
        error_code=job.error_code,
        reason=job.reason,
        message=job.message,
    )


@router.post("/analyze-job", response_model=AnalyzeJobResponse)
async def analyze_job(request: AnalyzeJobRequest) -> AnalyzeJobResponse:
    try:
        return await submit_analyze_job(request)
    except Exception:
        return AnalyzeJobResponse(
            job_id="",
            status="error",
            total_count=len(request.offers),
            accepted_count=0,
            rejected_count=len(request.offers),
            reason="internal error",
        )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    return get_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str) -> dict[str, Any]:
    return cancel_job_by_id(job_id)


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info_endpoint() -> ModelInfoResponse:
    try:
        return await asyncio.wait_for(get_model_info(), timeout=10)
    except asyncio.TimeoutError:
        return ModelInfoResponse(status="error", reason="timeout")
    except Exception:
        return ModelInfoResponse(status="error", reason="internal error")


@router.get("/route-analysis", response_model=RouteAnalysisResponse)
async def route_analysis_endpoint() -> RouteAnalysisResponse:
    pool = get_pool()
    if pool is None:
        return RouteAnalysisResponse(
            status="unavailable_db_pool",
            reason="db pool is unavailable",
        )
    try:
        items_raw = await asyncio.wait_for(
            get_all_route_analysis_snapshots(pool),
            timeout=15,
        )
    except asyncio.TimeoutError:
        return RouteAnalysisResponse(
            status="unavailable_timeout",
            reason="snapshot query timeout",
        )
    except Exception as exc:  # noqa: BLE001 - endpoint should fail soft.
        logger.warning("route_analysis endpoint error: %s", exc.__class__.__name__)
        return RouteAnalysisResponse(
            status="unavailable_db_query_error",
            reason=exc.__class__.__name__,
        )

    items = [RouteAnalysisItem(**item) for item in items_raw]
    top_status, available_count, generated_at, expires_at = summarize_route_analysis_status(items)
    return RouteAnalysisResponse(
        status=top_status,
        route_count=len(items),
        available_count=available_count,
        generated_at=generated_at,
        expires_at=expires_at,
        items=items,
    )
