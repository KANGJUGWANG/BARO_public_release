from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    trip_type: str
    return_date: Optional[str] = None


class FlightOffer(BaseModel):
    flight_number: Optional[str] = None
    airline_code: Optional[str]
    airline_name: Optional[str]
    dep_time: Optional[str]
    arr_time: Optional[str]
    duration_min: Optional[int]
    stops: int
    price_krw: Optional[int]
    aircraft: Optional[str]
    seller_type: Optional[str]


class SearchResponse(BaseModel):
    origin: str
    destination: str
    depart_date: str
    offers: list[FlightOffer]
    crawled_at: str
    error: Optional[str] = None
    retryable: Optional[bool] = None
    retry_after_sec: Optional[int] = None
