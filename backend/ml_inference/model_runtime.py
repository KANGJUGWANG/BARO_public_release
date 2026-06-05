"""Lazy model runtime helpers for BARO oneway inference.

Importing this module must not load pkl files. Model loading only happens inside
load_oneway_runtime().
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from core.config import settings
from ml_inference.oneway_adapter import (
    load_oneway_models,
    predict_oneway,
)

logger = logging.getLogger(__name__)

REQUIRED_ARTIFACTS = (
    "feature_columns.json",
    "oneway_threshold.json",
    "final_model_metadata.json",
    "enc_mappings.json",
)

_ONEWAY_RUNTIME_CACHE: dict[str, Any] | None = None


def get_model_dir(model_dir: str | Path | None = None) -> Path:
    if model_dir:
        return Path(model_dir).expanduser()
    configured = settings.model_dir or os.getenv("MODEL_DIR", "")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / "models" / "finaltest_clean_v1"


def load_oneway_artifacts(model_dir: str | Path | None = None) -> dict[str, Any]:
    root = get_model_dir(model_dir)
    missing = [name for name in REQUIRED_ARTIFACTS if not (root / name).exists()]
    if missing:
        return {
            "status": "unavailable_artifact_missing",
            "model_dir": str(root),
            "reason": f"missing artifacts: {missing}",
        }

    try:
        feature_columns = _read_json(root / "feature_columns.json")
        threshold = _read_json(root / "oneway_threshold.json")
        metadata = _read_json(root / "final_model_metadata.json")
        enc_mappings = _read_json(root / "enc_mappings.json")
    except Exception as exc:  # noqa: BLE001 - smoke output should carry reason.
        return {
            "status": "unavailable_artifact_parse_failed",
            "model_dir": str(root),
            "reason": exc.__class__.__name__,
        }

    return {
        "status": "ok",
        "model_dir": str(root),
        "feature_columns": feature_columns,
        "threshold": float(threshold["selected_threshold"]),
        "threshold_artifact": threshold,
        "metadata": metadata,
        "enc_mappings": enc_mappings,
    }


def load_oneway_runtime(model_dir: str | Path | None = None, use_cache: bool = True) -> dict[str, Any]:
    global _ONEWAY_RUNTIME_CACHE

    root = get_model_dir(model_dir)
    if use_cache and _ONEWAY_RUNTIME_CACHE is not None:
        if _ONEWAY_RUNTIME_CACHE.get("model_dir") == str(root):
            return {
                **_ONEWAY_RUNTIME_CACHE,
                "load_seconds": 0.0,
                "cache_hit": True,
            }

    started = time.perf_counter()
    try:
        models, artifacts = load_oneway_models(root)
    except Exception as exc:  # noqa: BLE001 - model load failure must stay local.
        return {
            "status": "unavailable_model_load_failed",
            "model_dir": str(root),
            "reason": exc.__class__.__name__,
        }

    runtime = {
        "status": "ok",
        "model_dir": str(root),
        "models": models,
        "artifacts": artifacts,
        "load_seconds": round(time.perf_counter() - started, 3),
        "cache_hit": False,
    }
    if use_cache:
        _ONEWAY_RUNTIME_CACHE = runtime
    logger.info("oneway runtime loaded in %.3f seconds", runtime["load_seconds"])
    return runtime


def predict_oneway_from_feature(feature_row: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    if runtime.get("status") != "ok":
        return {
            "prediction_status": runtime.get("status", "unavailable_model_load_failed"),
            "reason": runtime.get("reason"),
            "model_dir": runtime.get("model_dir"),
        }

    try:
        result = predict_oneway(feature_row, runtime["models"], runtime["artifacts"])
    except Exception as exc:  # noqa: BLE001 - smoke output should carry reason.
        return {
            "prediction_status": "prediction_failed",
            "reason": exc.__class__.__name__,
        }

    if result.get("feature_status") == "prediction_unavailable":
        return {
            "prediction_status": _unavailable_status(result.get("unavailable_reason")),
            "reason": result.get("unavailable_reason"),
            "details": result.get("details", {}),
        }

    decision = result.get("decision")
    wait_probability = result.get("wait_probability")
    confidence = _confidence(decision, wait_probability)

    return {
        "prediction_status": "ok",
        "decision": decision,
        "pred_saving": result.get("pred_saving"),
        "wait_probability": wait_probability,
        "threshold": result.get("threshold"),
        "confidence": confidence,
        "model_version": result.get("model_version"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _confidence(decision: str | None, wait_probability: Any) -> float | None:
    if wait_probability is None:
        return None
    probability = float(wait_probability)
    if decision == "WAIT":
        return probability
    if decision == "BUY":
        return 1.0 - probability
    return None


def _unavailable_status(reason: str | None) -> str:
    reason_text = reason or ""
    if "insufficient history" in reason_text:
        return "unavailable_insufficient_history"
    if "unknown encoding" in reason_text:
        return "unavailable_unknown_mapping"
    return "prediction_unavailable"


ROUNDTRIP_MODEL_FILES = (
    "roundtrip_stage1_xgboost.pkl",
    "roundtrip_stage2_xgboost.pkl",
)

ROUNDTRIP_ARTIFACT_FILES = (
    "feature_columns.json",
    "roundtrip_threshold.json",
    "enc_mappings.json",
)

_ROUNDTRIP_RUNTIME_CACHE: dict[str, Any] | None = None


def load_roundtrip_artifacts(model_dir: str | Path | None = None) -> dict[str, Any]:
    """
    Load roundtrip artifacts without loading pkl files.

    The roundtrip feature lists live under feature_columns["roundtrip"], and the
    decision threshold is selected_threshold from roundtrip_threshold.json.
    """
    root = get_model_dir(model_dir)

    missing_pkl = [name for name in ROUNDTRIP_MODEL_FILES if not (root / name).exists()]
    if missing_pkl:
        return {
            "status": "unavailable_artifact_missing",
            "model_dir": str(root),
            "reason": f"missing roundtrip pkl: {missing_pkl}",
        }

    missing_artifacts = [name for name in ROUNDTRIP_ARTIFACT_FILES if not (root / name).exists()]
    if missing_artifacts:
        return {
            "status": "unavailable_artifact_missing",
            "model_dir": str(root),
            "reason": f"missing roundtrip artifacts: {missing_artifacts}",
        }

    try:
        feature_columns = _read_json(root / "feature_columns.json")
        roundtrip_fc = feature_columns.get("roundtrip")
        if not roundtrip_fc:
            return {
                "status": "unavailable_artifact_missing",
                "model_dir": str(root),
                "reason": "feature_columns.json has no 'roundtrip' key",
            }

        threshold_data = _read_json(root / "roundtrip_threshold.json")
        if "selected_threshold" not in threshold_data:
            return {
                "status": "unavailable_artifact_missing",
                "model_dir": str(root),
                "reason": "roundtrip_threshold.json has no selected_threshold",
            }

        enc_mappings = _read_json(root / "enc_mappings.json")
        meta_path = root / "roundtrip_final_model_metadata.json"
        if not meta_path.exists():
            meta_path = root / "final_model_metadata.json"
        metadata = _read_json(meta_path) if meta_path.exists() else {}
    except Exception as exc:  # noqa: BLE001 - smoke output should carry reason.
        return {
            "status": "unavailable_artifact_parse_failed",
            "model_dir": str(root),
            "reason": exc.__class__.__name__,
        }

    return {
        "status": "ok",
        "model_dir": str(root),
        "feature_columns": feature_columns,
        "stage1_features": roundtrip_fc.get("stage1", []),
        "stage2_features": roundtrip_fc.get("stage2", []),
        "threshold": float(threshold_data["selected_threshold"]),
        "threshold_artifact": threshold_data,
        "enc_mappings": enc_mappings,
        "metadata": metadata,
    }


def load_roundtrip_runtime(model_dir: str | Path | None = None, use_cache: bool = True) -> dict[str, Any]:
    """
    Lazy-load roundtrip XGB/XGB runtime. This cache is independent from oneway.
    """
    global _ROUNDTRIP_RUNTIME_CACHE

    import joblib

    root = get_model_dir(model_dir)
    if use_cache and _ROUNDTRIP_RUNTIME_CACHE is not None:
        if _ROUNDTRIP_RUNTIME_CACHE.get("model_dir") == str(root):
            return {
                **_ROUNDTRIP_RUNTIME_CACHE,
                "load_seconds": 0.0,
                "cache_hit": True,
            }

    artifacts = load_roundtrip_artifacts(model_dir)
    if artifacts.get("status") != "ok":
        return artifacts

    started = time.perf_counter()
    try:
        models = {
            "stage1": joblib.load(root / ROUNDTRIP_MODEL_FILES[0]),
            "stage2": joblib.load(root / ROUNDTRIP_MODEL_FILES[1]),
        }
    except Exception as exc:  # noqa: BLE001 - model load failure must stay local.
        return {
            "status": "unavailable_model_load_failed",
            "model_dir": str(root),
            "reason": exc.__class__.__name__,
        }

    runtime = {
        "status": "ok",
        "model_dir": str(root),
        "models": models,
        "artifacts": artifacts,
        "load_seconds": round(time.perf_counter() - started, 3),
        "cache_hit": False,
    }
    if use_cache:
        _ROUNDTRIP_RUNTIME_CACHE = runtime
    logger.info("roundtrip runtime loaded in %.3f seconds", runtime["load_seconds"])
    return runtime


def predict_roundtrip_from_feature(feature_row: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    from ml_inference.roundtrip_adapter import predict_roundtrip

    if runtime.get("status") != "ok":
        return {
            "prediction_status": runtime.get("status", "unavailable_model_load_failed"),
            "reason": runtime.get("reason"),
            "model_dir": runtime.get("model_dir"),
        }

    try:
        result = predict_roundtrip(feature_row, runtime["models"], runtime["artifacts"])
    except Exception as exc:  # noqa: BLE001 - smoke output should carry reason.
        return {
            "prediction_status": "prediction_failed",
            "reason": exc.__class__.__name__,
        }

    if result.get("feature_status") == "prediction_unavailable":
        return {
            "prediction_status": "prediction_unavailable",
            "reason": result.get("unavailable_reason"),
        }

    decision = result.get("decision")
    wait_probability = result.get("wait_probability")
    confidence = _confidence(decision, wait_probability)

    return {
        "prediction_status": "ok",
        "decision": decision,
        "pred_saving": result.get("pred_saving"),
        "wait_probability": wait_probability,
        "threshold": result.get("threshold"),
        "confidence": confidence,
        "model_version": result.get("model_version"),
    }
