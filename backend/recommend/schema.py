from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RecommendSearchRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    trip_type: str = "oneway"
    max_predict_offers: Optional[int] = 3


class OfferInput(BaseModel):
    offer_observation_id: Optional[int] = None
    refresh_offer_id: Optional[int] = None
    source_offer_id: Optional[int] = None
    flight_number: Optional[str] = None
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None
    dep_time: Optional[str] = None
    dep_time_local: Optional[str] = None
    arr_time: Optional[str] = None
    arr_time_local: Optional[str] = None
    duration_min: Optional[int] = None
    stops: Optional[int] = 0
    price_krw: Optional[int] = None
    aircraft: Optional[str] = None
    seller_type: Optional[str] = None
    ret_flight_number: Optional[str] = None
    ret_airline_code: Optional[str] = None
    ret_dep_time_local: Optional[str] = None
    ret_arr_time_local: Optional[str] = None
    return_date: Optional[str] = None
    stay_nights: Optional[int] = None


class PredictOneRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    trip_type: str = "oneway"
    offer: OfferInput


class HistoryRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    trip_type: str = "oneway"
    offer: OfferInput


class PricePoint(BaseModel):
    observed_at: str
    dpd: int
    price_krw: int
    flight_number: Optional[str] = None
    ret_flight_number: Optional[str] = None
    airline_code: Optional[str] = None
    ret_airline_code: Optional[str] = None
    dep_time_local: Optional[str] = None
    ret_dep_time_local: Optional[str] = None


class HistorySummary(BaseModel):
    count: int
    min_price: int
    max_price: int
    mean_price: int
    latest_price: Optional[int] = None
    current_price: Optional[int] = None


class HistoryResponse(BaseModel):
    status: str
    trip_type: Optional[str] = None
    flight_number: Optional[str] = None
    ret_flight_number: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    depart_date: Optional[str] = None
    return_date: Optional[str] = None
    stay_nights: Optional[int] = None
    history: list[PricePoint] = Field(default_factory=list)
    summary: Optional[HistorySummary] = None
    reason: Optional[str] = None


class AnalyzeJobRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    trip_type: str = "oneway"
    offers: list[OfferInput]


class AnalyzeJobResponse(BaseModel):
    job_id: str
    status: str
    total_count: int
    accepted_count: int
    rejected_count: int = 0
    reason: Optional[str] = None


class RoundtripCandidatesRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    return_date: str
    stay_nights: Optional[int] = None
    limit: int = 20
    source_mode: Optional[str] = "auto"


class RoundtripCandidateOffer(BaseModel):
    offer_observation_id: Optional[int] = None
    refresh_offer_id: Optional[int] = None
    source_offer_id: Optional[int] = None
    flight_number: Optional[str] = None
    ret_flight_number: Optional[str] = None
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None
    ret_airline_code: Optional[str] = None
    dep_time_local: Optional[str] = None
    arr_time_local: Optional[str] = None
    ret_dep_time_local: Optional[str] = None
    ret_arr_time_local: Optional[str] = None
    duration_min: Optional[int] = None
    ret_duration_min: Optional[int] = None
    stops: Optional[int] = None
    price_krw: Optional[int] = None
    seller_domain: Optional[str] = None
    price_status: Optional[str] = None
    parse_status: Optional[str] = None


class RoundtripCandidatesResponse(BaseModel):
    status: str
    origin: str
    destination: str
    depart_date: str
    return_date: Optional[str] = None
    stay_nights: Optional[int] = None
    observed_at: Optional[str] = None
    source: Optional[str] = None
    source_label: Optional[str] = None
    is_realtime: Optional[bool] = None
    fallback_used: Optional[bool] = None
    expires_at: Optional[str] = None
    offers: list[RoundtripCandidateOffer] = Field(default_factory=list)
    reason: Optional[str] = None


class OnewayCandidatesRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    limit: int = 20
    source_mode: Optional[str] = "auto"


class OnewayCandidateOffer(BaseModel):
    offer_observation_id: Optional[int] = None
    refresh_offer_id: Optional[int] = None
    source_offer_id: Optional[int] = None
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None
    flight_number: Optional[str] = None
    dep_time: Optional[str] = None
    dep_time_local: Optional[str] = None
    arr_time: Optional[str] = None
    arr_time_local: Optional[str] = None
    duration_min: Optional[int] = None
    stops: Optional[int] = None
    price_krw: Optional[int] = None
    seller_domain: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type: Optional[str] = None
    price_source: Optional[str] = None
    price_status: Optional[str] = None
    parse_status: Optional[str] = None
    price_selection_reason: Optional[str] = None


class OnewayCandidatesResponse(BaseModel):
    status: str
    origin: str
    destination: str
    depart_date: str
    trip_type: str = "oneway"
    observed_at: Optional[str] = None
    source: Optional[str] = None
    source_label: Optional[str] = None
    is_realtime: Optional[bool] = None
    fallback_used: Optional[bool] = None
    expires_at: Optional[str] = None
    offers: list[OnewayCandidateOffer] = Field(default_factory=list)
    reason: Optional[str] = None


class RoundtripRefreshJobRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    return_date: Optional[str] = None
    stay_nights: int = 7
    force_refresh: bool = False
    timeout_seconds: int = 150


class RoundtripRefreshJobStartResponse(BaseModel):
    job_id: str
    status: str
    cache_key: Optional[str] = None
    origin: str
    destination: str
    depart_date: str
    return_date: Optional[str] = None
    stay_nights: int
    force_refresh: bool
    timeout_seconds: int
    started_at: Optional[str] = None
    latest_observed_at_before: Optional[str] = None
    fallback_available: bool = False
    message: Optional[str] = None
    reason: Optional[str] = None


class RoundtripRefreshJobStatusResponse(BaseModel):
    job_id: str
    status: str
    cache_key: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    depart_date: Optional[str] = None
    return_date: Optional[str] = None
    stay_nights: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    latest_observed_at_before: Optional[str] = None
    latest_observed_at_after: Optional[str] = None
    refreshed: bool = False
    candidates_available: int = 0
    fallback_available: bool = False
    error_code: Optional[str] = None
    reason: Optional[str] = None
    message: Optional[str] = None


class OnewayRefreshJobRequest(BaseModel):
    origin: str
    destination: str
    depart_date: str
    force_refresh: bool = False
    timeout_seconds: int = 150


class OnewayRefreshJobStartResponse(BaseModel):
    job_id: str
    status: str
    cache_key: Optional[str] = None
    origin: str
    destination: str
    depart_date: str
    force_refresh: bool
    timeout_seconds: int
    started_at: Optional[str] = None
    latest_observed_at_before: Optional[str] = None
    fallback_available: bool = False
    message: Optional[str] = None
    reason: Optional[str] = None


class OnewayRefreshJobStatusResponse(BaseModel):
    job_id: str
    status: str
    cache_key: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    depart_date: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    latest_observed_at_before: Optional[str] = None
    latest_observed_at_after: Optional[str] = None
    refreshed: bool = False
    candidates_available: int = 0
    fallback_available: bool = False
    error_code: Optional[str] = None
    reason: Optional[str] = None
    message: Optional[str] = None


class RouteAnalysisItem(BaseModel):
    route_key: str
    route_type: str
    origin: str
    destination: str
    stay_nights: Optional[int] = None
    status: str
    is_stale: Optional[bool] = None
    confidence: Optional[str] = None
    generated_at: Optional[str] = None
    expires_at: Optional[str] = None
    latest_observed_at: Optional[str] = None
    observation_count: Optional[int] = None
    valid_offer_count: Optional[int] = None
    summary: Optional[dict] = None
    dpd_curve: Optional[list] = None
    cheap_airlines: Optional[list] = None


class RouteAnalysisResponse(BaseModel):
    status: str
    route_count: int = 0
    available_count: int = 0
    generated_at: Optional[str] = None
    expires_at: Optional[str] = None
    items: list[RouteAnalysisItem] = Field(default_factory=list)
    reason: Optional[str] = None


class JobPredictionItemSchema(BaseModel):
    offer_observation_id: Optional[int] = None
    refresh_offer_id: Optional[int] = None
    source_offer_id: Optional[int] = None
    flight_number: Optional[str] = None
    dep_time: Optional[str] = None
    dep_time_local: Optional[str] = None
    ret_flight_number: Optional[str] = None
    ret_dep_time_local: Optional[str] = None
    return_date: Optional[str] = None
    stay_nights: Optional[int] = None
    price_krw: Optional[int] = None
    prediction: dict = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    predictions: list[JobPredictionItemSchema] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ModelInfoResponse(BaseModel):
    status: str
    model_version: Optional[str] = None
    models: dict = Field(default_factory=dict)
    scope: dict = Field(default_factory=dict)
    architecture: dict = Field(default_factory=dict)
    architecture_by_trip: dict = Field(default_factory=dict)
    features: dict = Field(default_factory=dict)
    features_by_trip: dict = Field(default_factory=dict)
    decision_policy: dict = Field(default_factory=dict)
    decision_policy_by_trip: dict = Field(default_factory=dict)
    artifacts: dict = Field(default_factory=dict)
    threshold_sources: dict = Field(default_factory=dict)
    dates: dict = Field(default_factory=dict)
    data: dict = Field(default_factory=dict)
    notice: str = "추천 결과는 구매 보조 정보이며 실제 가격을 보장하지 않습니다."
    reason: Optional[str] = None


class PredictionResult(BaseModel):
    prediction_status: str
    decision: Optional[str] = None
    pred_saving: Optional[float] = None
    wait_probability: Optional[float] = None
    threshold: Optional[float] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    reason: Optional[str] = None
    history_row_count: Optional[int] = None
    feature_status: Optional[str] = None


class RecommendedFlightOffer(BaseModel):
    flight_number: Optional[str] = None
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None
    dep_time: Optional[str] = None
    arr_time: Optional[str] = None
    duration_min: Optional[int] = None
    stops: int
    price_krw: Optional[int] = None
    aircraft: Optional[str] = None
    seller_type: Optional[str] = None
    prediction: PredictionResult


class RecommendSearchResponse(BaseModel):
    origin: str
    destination: str
    depart_date: str
    offers: list[RecommendedFlightOffer]
    crawled_at: str
    error: Optional[str] = None
