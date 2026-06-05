from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from crawler.collector import CrawlError, collect_oneway_realtime
from flights.schema import FlightOffer, SearchRequest, SearchResponse

ALLOWED_AIRPORTS = {"ICN", "NRT", "HND"}

log = logging.getLogger(__name__)


def _empty_response(request: SearchRequest, error: str) -> SearchResponse:
    return SearchResponse(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        offers=[],
        crawled_at=datetime.now().isoformat(timespec="seconds"),
        error=error,
    )


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else None
    return None


def _stops(value: Any) -> int:
    parsed = _int_or_none(value)
    return parsed if parsed is not None else 0


def _flight_number(card: dict) -> str | None:
    dep = card.get("dep") or {}
    candidates = [
        card.get("flight_number"),
        card.get("flight_no"),
        dep.get("flight_no"),
        dep.get("flight_number"),
    ]
    for value in candidates:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _to_offer(card: dict) -> FlightOffer:
    dep = card.get("dep") or {}
    return FlightOffer(
        flight_number=_flight_number(card),
        airline_code=card.get("airline_code"),
        airline_name=card.get("airline_name"),
        dep_time=dep.get("dep_time"),
        arr_time=dep.get("arr_time"),
        duration_min=_int_or_none(dep.get("duration_min")),
        stops=_stops(card.get("stops")),
        price_krw=_int_or_none(card.get("price_krw")),
        aircraft=dep.get("aircraft"),
        seller_type=card.get("seller_type") or "unknown",
    )


async def search_flights(request: SearchRequest) -> SearchResponse:
    origin = request.origin.upper().strip()
    destination = request.destination.upper().strip()
    trip_type = request.trip_type.lower().strip()

    normalized = SearchRequest(
        origin=origin,
        destination=destination,
        depart_date=request.depart_date.strip(),
        trip_type=trip_type,
    )

    if origin not in ALLOWED_AIRPORTS or destination not in ALLOWED_AIRPORTS:
        return _empty_response(normalized, "invalid route")
    if origin == destination:
        return _empty_response(normalized, "invalid route")
    if trip_type != "oneway":
        return _empty_response(normalized, "unsupported trip_type")

    try:
        dep_date = date.fromisoformat(normalized.depart_date)
    except ValueError:
        return _empty_response(normalized, "invalid depart_date")

    if dep_date < date.today():
        return _empty_response(normalized, "invalid depart_date")

    try:
        cards = await collect_oneway_realtime(origin, destination, dep_date)
        offers = [_to_offer(card) for card in cards]
    except CrawlError as exc:
        return _empty_response(normalized, exc.reason)
    except Exception:
        log.exception("Flight crawling failed")
        return _empty_response(normalized, "crawling failed")

    return SearchResponse(
        origin=origin,
        destination=destination,
        depart_date=normalized.depart_date,
        offers=offers,
        crawled_at=datetime.now().isoformat(timespec="seconds"),
        error=None,
    )
