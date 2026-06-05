from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter

from flights.schema import SearchRequest, SearchResponse
from flights.search_manager import build_search_key, search_managed
from flights.service import search_flights

router = APIRouter(tags=["flights"])


def _error_response(
    request: SearchRequest,
    error: str,
    retryable: bool = False,
    retry_after_sec: int | None = None,
) -> SearchResponse:
    return SearchResponse(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        offers=[],
        crawled_at=datetime.now().isoformat(timespec="seconds"),
        error=error,
        retryable=retryable or None,
        retry_after_sec=retry_after_sec,
    )


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    normalized_request = SearchRequest(
        origin=request.origin.upper().strip(),
        destination=request.destination.upper().strip(),
        depart_date=request.depart_date.strip(),
        trip_type=request.trip_type.lower().strip(),
        return_date=request.return_date.strip() if request.return_date else None,
    )
    search_key = build_search_key(
        origin=normalized_request.origin,
        destination=normalized_request.destination,
        depart_date=normalized_request.depart_date,
        trip_type=normalized_request.trip_type,
        return_date=normalized_request.return_date,
    )

    async def _crawl() -> SearchResponse:
        return await asyncio.wait_for(search_flights(normalized_request), timeout=120)

    try:
        result, is_retryable_busy = await search_managed(search_key, _crawl)
    except asyncio.TimeoutError:
        return _error_response(normalized_request, "crawling timeout")
    except Exception:
        return _error_response(normalized_request, "crawling failed")

    if is_retryable_busy:
        return _error_response(
            normalized_request,
            "crawler busy retryable",
            retryable=True,
            retry_after_sec=3,
        )

    if result is None:
        return _error_response(normalized_request, "crawling failed")

    return result
