from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.config import settings

REQUIRED_ARTIFACTS = (
    "feature_columns.json",
    "oneway_threshold.json",
    "roundtrip_threshold.json",
    "final_model_metadata.json",
    "enc_mappings.json",
)

PKL_FILES_BY_TRIP = {
    "oneway": {
        "stage1": "oneway_stage1_random_forest.pkl",
        "stage2": "oneway_stage2_xgboost.pkl",
    },
    "roundtrip": {
        "stage1": "roundtrip_stage1_xgboost.pkl",
        "stage2": "roundtrip_stage2_xgboost.pkl",
    },
}


def _default_model_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "models" / "finaltest_clean_v1"


def _model_dir() -> Path:
    configured = settings.model_dir or os.getenv("MODEL_DIR", "")
    return Path(configured).expanduser() if configured else _default_model_dir()


def _artifact_status(path: Path) -> dict[str, Any]:
    exists = path.exists()
    status: dict[str, Any] = {
        "exists": exists,
        "parseable": False,
    }
    if not exists:
        return status

    try:
        json.loads(path.read_text(encoding="utf-8"))
        status["parseable"] = True
    except Exception as exc:
        status["error"] = exc.__class__.__name__
    return status


def _pkl_status(path: Path) -> dict[str, Any]:
    exists = path.exists()
    status: dict[str, Any] = {"exists": exists}
    if exists:
        status["size_mb"] = round(path.stat().st_size / (1024 * 1024), 1)
    return status


def check_model_status() -> dict[str, Any]:
    model_dir = _model_dir()
    artifacts = {
        name: _artifact_status(model_dir / name)
        for name in REQUIRED_ARTIFACTS
    }
    pkl_files_by_trip = {
        trip_type: {
            stage: _pkl_status(model_dir / file_name)
            for stage, file_name in files.items()
        }
        for trip_type, files in PKL_FILES_BY_TRIP.items()
    }
    pkl_files = {
        file_name: pkl_files_by_trip["oneway"][stage]
        for stage, file_name in PKL_FILES_BY_TRIP["oneway"].items()
    }

    return {
        "model_loaded": False,
        "model_dir": str(model_dir),
        "artifact_parse_ok": all(
            item["exists"] and item["parseable"]
            for item in artifacts.values()
        ),
        "artifacts": artifacts,
        "pkl_files": pkl_files,
        "pkl_files_by_trip": pkl_files_by_trip,
    }
