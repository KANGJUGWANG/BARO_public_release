from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

BANNED_FEATURE_TOKENS = ("cv_pct", "saving_pct", "label", "pred_margin", "future_obs_count")

REQUIRED_ARTIFACTS = (
    "feature_columns.json",
    "oneway_threshold.json",
    "final_model_metadata.json",
    "enc_mappings.json",
)

REQUIRED_MODEL_FILES = (
    "oneway_stage1_random_forest.pkl",
    "oneway_stage2_xgboost.pkl",
)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_time(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 5:
        return text[:5]
    return text


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_origin_destination(request: dict[str, Any], offer: dict[str, Any]) -> tuple[str | None, str | None]:
    origin = (
        request.get("origin")
        or request.get("origin_iata")
        or offer.get("origin")
        or offer.get("origin_iata")
    )
    destination = (
        request.get("destination")
        or request.get("destination_iata")
        or request.get("dest")
        or offer.get("destination")
        or offer.get("destination_iata")
        or offer.get("dest")
    )
    return (
        str(origin).upper().strip() if origin else None,
        str(destination).upper().strip() if destination else None,
    )


def _mapping_payload(artifacts: dict[str, Any]) -> dict[str, dict[str, int]]:
    payload = artifacts.get("enc_mappings", {})
    if "mappings" in payload:
        payload = payload["mappings"]
    return {
        "route_enc": {str(k): int(v) for k, v in payload.get("route_enc", {}).items()},
        "route_pair_enc": {str(k): int(v) for k, v in payload.get("route_pair_enc", {}).items()},
        "airline_enc": {str(k): int(v) for k, v in payload.get("airline_enc", {}).items()},
        "flight_enc": {str(k): int(v) for k, v in payload.get("flight_enc", {}).items()},
        "flight_number_key": {str(k): str(v) for k, v in payload.get("flight_number_key", {}).items()},
    }


def _resolve_route_encoding(
    request: dict[str, Any],
    offer: dict[str, Any],
    mappings: dict[str, dict[str, int]],
) -> tuple[str | None, int | None]:
    route = offer.get("route") or request.get("route") or request.get("route_key")
    if route and str(route) in mappings["route_enc"]:
        route_text = str(route)
        return route_text, mappings["route_enc"][route_text]

    origin, destination = _extract_origin_destination(request, offer)
    if not origin or not destination:
        return (str(route), None) if route else (None, None)

    route_pair = f"{origin}_{destination}"
    if route_pair in mappings.get("route_pair_enc", {}):
        return route_pair, mappings["route_pair_enc"][route_pair]

    matches = []
    for candidate in mappings["route_enc"]:
        upper = candidate.upper()
        origin_idx = upper.find(origin)
        destination_idx = upper.find(destination)
        if origin_idx >= 0 and destination_idx >= 0 and origin_idx < destination_idx:
            matches.append(candidate)
    if len(matches) == 1:
        return matches[0], mappings["route_enc"][matches[0]]
    return (str(route), None) if route else (None, None)


def _extract_airline(offer: dict[str, Any]) -> str | None:
    value = offer.get("airline_code") or _nested_get(offer, "dep", "airline_code")
    return str(value).strip() if value else None


def _extract_flight_key(offer: dict[str, Any]) -> str | None:
    direct = offer.get("flight_key")
    if direct:
        return str(direct).strip()
    flight_number = (
        offer.get("flight_number")
        or offer.get("flight_no")
        or _nested_get(offer, "dep", "flight_no")
        or _nested_get(offer, "dep", "flight_number")
    )
    dep_time = (
        offer.get("dep_time_local")
        or offer.get("dep_time")
        or _nested_get(offer, "dep", "dep_time")
        or _nested_get(offer, "dep", "dep_time_local")
    )
    dep_time_norm = _normalize_time(dep_time)
    if not flight_number or not dep_time_norm:
        return None
    return f"{str(flight_number).strip()}_{dep_time_norm}"


def _resolve_flight_key(offer: dict[str, Any], mappings: dict[str, dict[str, int]]) -> str | None:
    direct = _extract_flight_key(offer)
    if direct in mappings["flight_enc"]:
        return direct

    flight_number = (
        offer.get("flight_number")
        or offer.get("flight_no")
        or _nested_get(offer, "dep", "flight_no")
        or _nested_get(offer, "dep", "flight_number")
    )
    if not flight_number:
        return direct
    flight_number_text = str(flight_number).strip()
    mapped = mappings.get("flight_number_key", {}).get(flight_number_text)
    if mapped:
        return mapped
    prefix = f"{flight_number_text}_"
    matches = [key for key in mappings["flight_enc"] if key.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return direct


def _unavailable(reason: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "feature_status": "prediction_unavailable",
        "unavailable_reason": reason,
        "details": details or {},
        "feature_row": None,
    }


def _artifact_paths(model_dir: Path, metadata: dict[str, Any]) -> tuple[Path, Path]:
    stage1 = model_dir / REQUIRED_MODEL_FILES[0]
    stage2 = model_dir / REQUIRED_MODEL_FILES[1]
    if stage1.exists() and stage2.exists():
        return stage1, stage2

    mode_meta = metadata.get("metadata", {}).get("modes", {}).get("oneway", {})
    pkl_paths = mode_meta.get("model_pkl_paths", {})
    meta_stage1 = Path(pkl_paths.get("stage1", "")) if pkl_paths.get("stage1") else stage1
    meta_stage2 = Path(pkl_paths.get("stage2", "")) if pkl_paths.get("stage2") else stage2
    return meta_stage1, meta_stage2


def _validate_feature_columns(feature_columns: dict[str, Any]) -> None:
    mode_cols = feature_columns.get("oneway")
    if not mode_cols:
        raise ValueError("feature_columns.json does not contain oneway columns")
    for stage in ("stage1", "stage2"):
        cols = mode_cols.get(stage, [])
        for col in cols:
            if any(token in col for token in BANNED_FEATURE_TOKENS):
                raise ValueError(f"banned feature found in {stage}: {col}")


def load_oneway_models(model_dir: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    import joblib

    root = Path(model_dir)
    missing = [name for name in REQUIRED_ARTIFACTS if not (root / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required oneway inference artifacts in {root}: {missing}")

    feature_columns = _read_json(root / "feature_columns.json")
    threshold = _read_json(root / "oneway_threshold.json")
    metadata = _read_json(root / "final_model_metadata.json")
    enc_mappings = _read_json(root / "enc_mappings.json")
    _validate_feature_columns(feature_columns)

    stage1_path, stage2_path = _artifact_paths(root, metadata)
    missing_models = [str(path) for path in [stage1_path, stage2_path] if not path.exists()]
    if missing_models:
        raise FileNotFoundError(f"Missing oneway model .pkl files: {missing_models}")

    models = {
        "stage1": joblib.load(stage1_path),
        "stage2": joblib.load(stage2_path),
    }
    artifacts = {
        "model_dir": str(root),
        "stage1_path": str(stage1_path),
        "stage2_path": str(stage2_path),
        "feature_columns": feature_columns,
        "threshold": float(threshold["selected_threshold"]),
        "threshold_artifact": threshold,
        "metadata": metadata,
        "enc_mappings": enc_mappings,
    }
    return models, artifacts


def build_oneway_features(
    offer: Any,
    request: Any,
    history_rows: list[dict[str, Any]],
    now: datetime | None,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import pandas as pd

    if artifacts is None:
        return _unavailable("enc_mappings artifact is required to build inference features")

    offer_dict = _as_dict(offer)
    request_dict = _as_dict(request)
    mappings = _mapping_payload(artifacts)
    now_dt = now or datetime.now()

    route, route_enc = _resolve_route_encoding(request_dict, offer_dict, mappings)
    airline_code = _extract_airline(offer_dict)
    flight_key = _resolve_flight_key(offer_dict, mappings)
    price_krw = _int_or_none(offer_dict.get("price_krw"))
    depart_date = _parse_date(
        offer_dict.get("departure_date")
        or request_dict.get("depart_date")
        or request_dict.get("departure_date")
    )

    missing_identity = [
        name
        for name, value in {
            "route": route,
            "airline_code": airline_code,
            "flight_key": flight_key,
            "price_krw": price_krw,
            "departure_date": depart_date,
        }.items()
        if value is None
    ]
    if missing_identity:
        return _unavailable("missing required current offer fields", {"missing": missing_identity})

    unknown = {}
    if route_enc is None:
        unknown["route"] = route
    if airline_code not in mappings["airline_enc"]:
        unknown["airline_code"] = airline_code
    if flight_key not in mappings["flight_enc"]:
        unknown["flight_key"] = flight_key
    if unknown:
        return _unavailable("unknown encoding category", unknown)

    observed_at = _parse_datetime(offer_dict.get("observed_at")) or now_dt
    dpd = _int_or_none(offer_dict.get("dpd"))
    if dpd is None:
        dpd = max((depart_date - observed_at.date()).days, 0)

    current_row = {
        "traj_id": offer_dict.get("traj_id") or f"{route}_{flight_key}_{depart_date.isoformat()}",
        "route": route,
        "airline_code": airline_code,
        "flight_key": flight_key,
        "departure_date": depart_date.isoformat(),
        "observed_at": observed_at,
        "dpd": dpd,
        "price_krw": price_krw,
        "_is_current": True,
    }

    normalized_history = []
    for idx, row in enumerate(history_rows or []):
        hist = dict(row)
        hist_price = _int_or_none(hist.get("price_krw"))
        hist_observed = _parse_datetime(hist.get("observed_at"))
        hist_dpd = _int_or_none(hist.get("dpd"))
        if hist_price is None or hist_observed is None or hist_dpd is None:
            continue
        normalized_history.append(
            {
                "traj_id": current_row["traj_id"],
                "route": hist.get("route") or route,
                "airline_code": hist.get("airline_code") or airline_code,
                "flight_key": hist.get("flight_key") or flight_key,
                "departure_date": str(hist.get("departure_date") or current_row["departure_date"])[:10],
                "observed_at": hist_observed,
                "dpd": hist_dpd,
                "price_krw": hist_price,
                "_is_current": False,
                "_history_index": idx,
            }
        )

    rows = normalized_history + [current_row]
    if len(rows) < 7:
        return _unavailable(
            "insufficient history_rows for price_chg_6",
            {"required_total_rows": 7, "available_total_rows": len(rows)},
        )

    df = pd.DataFrame(rows).sort_values(["observed_at", "_is_current"], kind="mergesort").reset_index(drop=True)
    df["scan_hour"] = pd.to_datetime(df["observed_at"]).dt.hour
    df["scan_seq"] = df.groupby(["traj_id", "dpd"]).cumcount()
    df["dpd_max"] = df.groupby("traj_id")["dpd"].transform("max")
    df["dpd_ratio"] = df["dpd"] / df["dpd_max"].clip(lower=1)

    grouped = df.groupby("traj_id")["price_krw"]
    df["cum_min"] = grouped.transform(lambda x: x.expanding().min())
    df["cum_max"] = grouped.transform(lambda x: x.expanding().max())
    df["cum_mean"] = grouped.transform(lambda x: x.expanding().mean())
    df["cum_std"] = grouped.transform(lambda x: x.expanding().std().fillna(0))
    df["cum_count"] = grouped.transform(lambda x: x.expanding().count())
    df["price_pct_from_cum_min"] = (df["price_krw"] - df["cum_min"]) / df["cum_min"] * 100
    df["price_pct_from_cum_max"] = (df["price_krw"] - df["cum_max"]) / df["cum_max"] * 100
    df["price_pct_from_cum_mean"] = (df["price_krw"] - df["cum_mean"]) / df["cum_mean"] * 100
    df["price_chg_1"] = grouped.pct_change(1) * 100
    df["price_chg_3"] = grouped.pct_change(3) * 100
    df["price_chg_6"] = grouped.pct_change(6) * 100
    df["route_enc"] = route_enc
    df["airline_enc"] = mappings["airline_enc"][airline_code]
    df["flight_enc"] = mappings["flight_enc"][flight_key]

    current = df[df["_is_current"]].tail(1)
    if current.empty:
        return _unavailable("current row was not found after feature build")

    feature_columns = artifacts.get("feature_columns", {}).get("oneway", {}).get("stage1", [])
    missing_features = [col for col in feature_columns if col not in current.columns]
    if missing_features:
        return _unavailable("missing required stage1 feature columns", {"missing": missing_features})
    null_features = [col for col in feature_columns if pd.isna(current.iloc[0][col])]
    if null_features:
        return _unavailable("null required stage1 feature columns", {"null_features": null_features})

    feature_row = {col: current.iloc[0][col].item() if hasattr(current.iloc[0][col], "item") else current.iloc[0][col] for col in feature_columns}
    return {
        "feature_status": "ok",
        "unavailable_reason": None,
        "feature_row": feature_row,
        "metadata": {
            "route": route,
            "airline_code": airline_code,
            "flight_key": flight_key,
            "history_row_count": len(normalized_history),
            "cum_count": float(current.iloc[0]["cum_count"]),
        },
    }


def _predict_wait_proba(model: Any, frame: Any) -> float:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(frame)
        return float(proba[:, 1][0])
    pred = model.predict(frame)
    return float(pred[0])


def predict_oneway(feature_row: dict[str, Any], models: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    import pandas as pd

    if not feature_row:
        return {
            "feature_status": "prediction_unavailable",
            "decision": None,
            "unavailable_reason": "empty feature_row",
        }

    if feature_row.get("feature_status") == "prediction_unavailable":
        return {
            "feature_status": "prediction_unavailable",
            "decision": None,
            "unavailable_reason": feature_row.get("unavailable_reason"),
            "details": feature_row.get("details", {}),
        }
    if "feature_row" in feature_row:
        feature_row = feature_row["feature_row"]

    banned = [col for col in feature_row if any(token in col for token in BANNED_FEATURE_TOKENS)]
    if banned:
        raise ValueError(f"banned leakage/meta columns passed to predict_oneway: {banned}")

    cols = artifacts["feature_columns"]["oneway"]
    stage1_cols = cols["stage1"]
    stage2_cols = cols["stage2"]
    missing_stage1 = [col for col in stage1_cols if col not in feature_row]
    if missing_stage1:
        raise ValueError(f"missing stage1 features: {missing_stage1}")

    stage1_frame = pd.DataFrame([{col: feature_row[col] for col in stage1_cols}])
    pred_saving = float(models["stage1"].predict(stage1_frame)[0])

    stage2_row = dict(feature_row)
    stage2_row["pred_saving"] = pred_saving
    missing_stage2 = [col for col in stage2_cols if col not in stage2_row]
    if missing_stage2:
        raise ValueError(f"missing stage2 features: {missing_stage2}")
    stage2_frame = pd.DataFrame([{col: stage2_row[col] for col in stage2_cols}])
    wait_probability = _predict_wait_proba(models["stage2"], stage2_frame)
    threshold = float(artifacts["threshold"])
    decision = "WAIT" if wait_probability > threshold else "BUY"

    return {
        "feature_status": "ok",
        "decision": decision,
        "pred_saving": pred_saving,
        "wait_probability": wait_probability,
        "threshold": threshold,
        "model_version": (
            artifacts.get("metadata", {}).get("model_version")
            or artifacts.get("metadata", {}).get("run_id")
            or "unknown"
        ),
    }
