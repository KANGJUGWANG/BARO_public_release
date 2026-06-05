from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

MAPPING_SPECS = {
    "route_enc": ("route", "route_enc"),
    "airline_enc": ("airline_code", "airline_enc"),
    "flight_enc": ("flight_key", "flight_enc"),
}


def _build_mapping(df: pd.DataFrame, raw_col: str, enc_col: str) -> dict[str, int]:
    conflicts = (
        df[[raw_col, enc_col]]
        .dropna()
        .groupby(raw_col)[enc_col]
        .nunique()
    )
    conflict_keys = conflicts[conflicts > 1].index.astype(str).tolist()
    if conflict_keys:
        raise ValueError(f"{raw_col}->{enc_col} has conflicting encodings: {conflict_keys[:20]}")

    mapping = (
        df[[raw_col, enc_col]]
        .dropna()
        .drop_duplicates()
        .sort_values(raw_col)
    )
    return {str(row[raw_col]): int(row[enc_col]) for _, row in mapping.iterrows()}


def build_enc_mappings(source_csv: Path) -> dict:
    usecols = sorted({col for cols in MAPPING_SPECS.values() for col in cols} | {"traj_id"})
    df = pd.read_csv(source_csv, usecols=usecols)
    mappings = {
        name: _build_mapping(df, raw_col, enc_col)
        for name, (raw_col, enc_col) in MAPPING_SPECS.items()
    }
    route_pair = df["traj_id"].astype(str).str.extract(r"^([^_]+)_([^_]+)_")
    route_pair_df = pd.DataFrame({
        "route_pair": route_pair[0].astype(str) + "_" + route_pair[1].astype(str),
        "route_enc": df["route_enc"],
    })
    conflicts = route_pair_df.groupby("route_pair")["route_enc"].nunique()
    conflict_keys = conflicts[conflicts > 1].index.astype(str).tolist()
    if conflict_keys:
        raise ValueError(f"route_pair->route_enc has conflicting encodings: {conflict_keys[:20]}")
    mappings["route_pair_enc"] = {
        str(row["route_pair"]): int(row["route_enc"])
        for _, row in route_pair_df.dropna().drop_duplicates().sort_values("route_pair").iterrows()
    }
    flight_keys = pd.Series(list(mappings["flight_enc"].keys()), dtype="string")
    flight_number_df = pd.DataFrame({
        "flight_number": flight_keys.str.split("_", n=1).str[0],
        "flight_key": flight_keys,
    }).dropna()
    flight_key_counts = flight_number_df.groupby("flight_number")["flight_key"].nunique()
    unique_flight_numbers = set(flight_key_counts[flight_key_counts == 1].index.astype(str))
    mappings["flight_number_key"] = {
        str(row["flight_number"]): str(row["flight_key"])
        for _, row in flight_number_df.drop_duplicates().sort_values("flight_number").iterrows()
        if str(row["flight_number"]) in unique_flight_numbers
    }
    ambiguous_flight_numbers = flight_key_counts[flight_key_counts > 1].index.astype(str).tolist()
    return {
        "source_csv": str(source_csv),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mapping_specs": MAPPING_SPECS,
        "mappings": mappings,
        "normalization_notes": {
            "route_pair_enc": "Derived from traj_id origin/destination tokens to avoid relying on route display text.",
            "flight_number_key": "Only flight numbers with exactly one observed finaltest flight_key are mapped.",
            "ambiguous_flight_numbers": ambiguous_flight_numbers,
        },
        "counts": {name: len(values) for name, values in mappings.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build oneway inference encoding mappings from finaltest feature CSV.")
    parser.add_argument("--source-csv", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if not args.source_csv.exists():
        raise FileNotFoundError(args.source_csv)
    payload = build_enc_mappings(args.source_csv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    print(json.dumps(payload["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
