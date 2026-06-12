#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import shutil
import time
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "baro-repro-db-v1"
TOOL_VERSION = "phase3.6-c4.1r4"
REDACTED_SEARCH_URL = "<REDACTED_SEARCH_URL>"
CHUNK_SIZE = 1024 * 1024

EXIT_SUCCESS = 0
EXIT_INVALID = 2
EXIT_DB = 3
EXIT_INTEGRITY = 4
EXIT_UNSAFE = 5
EXIT_EXPORT = 6
EXIT_CONFLICT = 7
EXIT_PARTIAL = 8
EXIT_RELATION = 9
EXIT_LIMIT = 10

SOURCE_TABLE_COLUMNS = {
    "search_observation": [
        "observation_id", "observed_at", "source", "route_type", "origin_iata", "destination_iata",
        "departure_date", "return_date", "stay_nights", "dpd", "crawl_status", "search_url", "raw_file_path", "created_at",
    ],
    "flight_offer_observation": [
        "offer_observation_id", "observation_id", "card_index", "airline_code", "airline_name", "flight_number",
        "dep_time_local", "arr_time_local", "duration_min", "ret_airline_code", "ret_airline_name",
        "ret_flight_number", "ret_dep_time_local", "ret_arr_time_local", "ret_duration_min", "stops",
        "aircraft", "seller_domain", "selected_seller_name", "seller_type", "airline_tag_present",
        "price_krw", "price_source", "price_status", "parse_status", "price_selection_reason", "created_at",
    ],
    "service_route_analysis_snapshot": [
        "snapshot_id", "route_key", "route_type", "origin_iata", "destination_iata", "stay_nights",
        "analysis_version", "generated_at", "expires_at", "source_latest_observed_at", "observation_count",
        "valid_offer_count", "status", "confidence_label", "summary_json", "dpd_curve_json",
        "airline_ranking_json", "payload_json", "created_at", "updated_at",
    ],
}

SNAPSHOT_TABLE_COLUMNS = {
    table: list(columns) for table, columns in SOURCE_TABLE_COLUMNS.items()
}

TABLES = SNAPSHOT_TABLE_COLUMNS
REQUIRED_TABLES = ["search_observation", "flight_offer_observation"]
OPTIONAL_TABLES = ["service_route_analysis_snapshot"]
PRIVATE_PATTERNS = ["http://", "https://", "/home/", "C:\\Users\\", "10.145.", "134.185."]


class SnapshotError(Exception):
    exit_code = EXIT_INVALID
    public_code: str | None = None

    def __init__(self, message: str, exit_code: int | None = None, public_code: str | None = None):
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code
        if public_code is not None:
            self.public_code = public_code


class SchemaContractError(SnapshotError):
    exit_code = EXIT_INVALID
    public_code = "schema_contract_mismatch"


def reproduction_root() -> Path:
    return Path(__file__).resolve().parents[1]


def database_root() -> Path:
    return reproduction_root() / "database"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def safe_relative(value: str) -> Path:
    p = Path(value.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        raise SnapshotError("unsafe relative path", EXIT_UNSAFE)
    return p


def contained(root: Path, rel: str | Path) -> Path:
    base = root.resolve()
    target = (base / safe_relative(str(rel))).resolve(strict=False)
    if base != target and base not in target.parents:
        raise SnapshotError("path escapes root", EXIT_UNSAFE)
    return target


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def sanitize_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    clean = {k: row.get(k) for k in SNAPSHOT_TABLE_COLUMNS[table]}
    if table == "search_observation":
        clean["search_url"] = REDACTED_SEARCH_URL if clean.get("search_url") is not None else None
        clean["raw_file_path"] = None
    if table == "flight_offer_observation":
        clean["seller_domain"] = None
    return clean


def scan_forbidden(value: Any) -> bool:
    if value is None:
        return False
    text = str(value)
    return any(p in text for p in PRIVATE_PATTERNS)


def write_jsonl_gz(path: Path, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    uncompressed = 0
    with gzip.GzipFile(filename="", mode="wb", fileobj=path.open("wb"), mtime=0) as gz:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, sort_keys=True, default=json_default, separators=(",", ":")) + "\n"
            data = line.encode("utf-8")
            gz.write(data)
            count += 1
            uncompressed += len(data)
    return count, uncompressed


def iter_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _import_optional(module_name: str):
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        return None


def choose_db_driver(requested: str | None = None) -> str:
    choice = (requested or os.environ.get("BARO_DB_DRIVER") or "auto").strip().lower()
    if choice not in {"auto", "aiomysql", "pymysql"}:
        raise SnapshotError("invalid DB driver; expected auto, aiomysql, or pymysql", EXIT_INVALID)
    available = {
        "aiomysql": _import_optional("aiomysql") is not None,
        "pymysql": _import_optional("pymysql") is not None,
    }
    if choice == "auto":
        if available["aiomysql"]:
            return "aiomysql"
        if available["pymysql"]:
            return "pymysql"
        raise SnapshotError("no supported DB driver available: install aiomysql or pymysql", EXIT_DB)
    if not available[choice]:
        raise SnapshotError(f"requested DB driver unavailable: {choice}", EXIT_DB)
    return choice


class _PyMySQLCursorAdapter:
    def __init__(self, conn, cursor_class):
        self._conn = conn
        self._cursor_class = cursor_class
        self._cursor = None
        self.description = None

    async def __aenter__(self):
        self._cursor = self._conn.cursor(self._cursor_class)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._cursor is not None:
            self._cursor.close()
        self._cursor = None
        return False

    async def execute(self, sql: str, params: tuple[Any, ...] = ()):
        self._cursor.execute(sql, params)
        self.description = self._cursor.description

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchmany(self, size: int = 500):
        return self._cursor.fetchmany(size)


class _PyMySQLConnectionAdapter:
    driver_name = "pymysql"

    def __init__(self, raw_conn, cursor_class):
        self._raw_conn = raw_conn
        self._cursor_class = cursor_class

    def cursor(self):
        return _PyMySQLCursorAdapter(self._raw_conn, self._cursor_class)

    async def rollback(self):
        self._raw_conn.rollback()

    def close(self):
        self._raw_conn.close()


async def connect_from_env(prefix: str, driver: str | None = None):
    selected = choose_db_driver(driver)
    host = os.environ.get(prefix + "_HOST")
    port = int(os.environ.get(prefix + "_PORT", "3306"))
    db = os.environ.get(prefix + "_NAME")
    user = os.environ.get(prefix + "_USER")
    password = os.environ.get(prefix + "_PASSWORD")
    if not all([host, db, user, password]):
        raise SnapshotError(f"missing DB env for {prefix}", EXIT_DB)
    if selected == "aiomysql":
        import aiomysql
        return await aiomysql.connect(host=host, port=port, user=user, password=password, db=db, autocommit=False)
    import pymysql
    raw = pymysql.connect(host=host, port=port, user=user, password=password, database=db, autocommit=False, charset="utf8mb4")
    return _PyMySQLConnectionAdapter(raw, pymysql.cursors.SSCursor)


async def fetch_all(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = []
        while True:
            chunk = await cur.fetchmany(500)
            if not chunk:
                break
            rows.extend(dict(zip(cols, r)) for r in chunk)
        return rows


def snapshot_manifest(tier: str, snapshot_version: str, files: list[dict[str, Any]], tables: list[dict[str, Any]], selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_version": snapshot_version,
        "tier": tier,
        "reproduction_version": (reproduction_root() / "VERSION").read_text(encoding="utf-8").strip(),
        "source_commit": "f11e8e8",
        "public_commit": "12f5028",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sanitization_policy_version": "sanitized-db-v1",
        "selection": selection,
        "tables": tables,
        "total_rows": sum(t["row_count"] for t in tables),
        "total_uncompressed_bytes": sum(f["uncompressed_bytes"] for f in files),
        "files": files,
        "validation": {"required_tables": REQUIRED_TABLES, "optional_tables": OPTIONAL_TABLES},
        "status": "ready",
    }


def verify_snapshot(snapshot_root: Path, tier: str | None = None, strict: bool = False, deep: bool = False) -> dict[str, Any]:
    manifest_path = snapshot_root / "snapshot_manifest.json"
    if not manifest_path.exists():
        raise SnapshotError("snapshot_manifest.json missing", EXIT_INTEGRITY)
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotError("schema version mismatch", EXIT_INTEGRITY)
    if tier and manifest.get("tier") != tier:
        raise SnapshotError("tier mismatch", EXIT_INTEGRITY)
    table_counts: dict[str, int] = {}
    search_ids: set[Any] = set()
    offer_obs_ids: set[Any] = set()
    for file_info in manifest.get("files", []):
        rel = file_info["relative_path"]
        path = contained(snapshot_root, rel)
        if not path.exists():
            raise SnapshotError(f"snapshot file missing: {rel}", EXIT_INTEGRITY)
        if path.stat().st_size != file_info["size_bytes"]:
            raise SnapshotError(f"snapshot file size mismatch: {rel}", EXIT_INTEGRITY)
        if sha256_file(path) != file_info["sha256"]:
            raise SnapshotError(f"snapshot file sha mismatch: {rel}", EXIT_INTEGRITY)
        table = file_info["table"]
        count = 0
        seen_pk: set[Any] = set()
        pk = "observation_id" if table == "search_observation" else "offer_observation_id" if table == "flight_offer_observation" else "snapshot_id"
        for row in iter_jsonl_gz(path):
            count += 1
            if pk in row:
                if row[pk] in seen_pk:
                    raise SnapshotError(f"duplicate PK in {table}", EXIT_INTEGRITY)
                seen_pk.add(row[pk])
            for value in row.values():
                if scan_forbidden(value):
                    raise SnapshotError(f"forbidden value pattern in {table}", EXIT_UNSAFE)
            if table == "search_observation":
                if row.get("search_url") not in (None, REDACTED_SEARCH_URL):
                    raise SnapshotError("search_url not sanitized", EXIT_UNSAFE)
                if row.get("raw_file_path") is not None:
                    raise SnapshotError("raw_file_path not sanitized", EXIT_UNSAFE)
                search_ids.add(row["observation_id"])
            if table == "flight_offer_observation":
                if row.get("seller_domain") is not None:
                    raise SnapshotError("seller_domain not sanitized", EXIT_UNSAFE)
                offer_obs_ids.add(row["observation_id"])
        if count != file_info["row_count"]:
            raise SnapshotError(f"row count mismatch: {table}", EXIT_INTEGRITY)
        table_counts[table] = count
    missing_required = [t for t in REQUIRED_TABLES if t not in table_counts]
    if missing_required:
        raise SnapshotError("required table missing: " + ",".join(missing_required), EXIT_INTEGRITY)
    if not offer_obs_ids.issubset(search_ids):
        raise SnapshotError("orphan offer observation_id", EXIT_RELATION)
    if strict:
        expected = {f["relative_path"] for f in manifest.get("files", [])} | {"snapshot_manifest.json", "schema.sql"}
        actual = {p.relative_to(snapshot_root).as_posix() for p in snapshot_root.rglob("*") if p.is_file()}
        extra = actual - expected
        if extra:
            raise SnapshotError("unexpected snapshot file: " + sorted(extra)[0], EXIT_UNSAFE)
    return {"manifest": manifest, "table_counts": table_counts, "total_rows": sum(table_counts.values())}


def print_result(payload: dict[str, Any], json_output: bool = False, quiet: bool = False) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    elif not quiet:
        for k, v in payload.items():
            print(f"{k}={json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v}")


# C4.1H bounded selector support
from dataclasses import dataclass
import re as _re

EXIT_COVERAGE = 11
EXIT_UNBOUNDED = 12
QUERY_COMPILER_VERSION = "bounded-selector-v1"
_IATA_RE = _re.compile(r"^[A-Z]{3}$")
_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

@dataclass(frozen=True)
class SafetyLimits:
    max_search_rows: int
    max_offer_rows: int
    max_optional_rows: int
    max_total_rows: int
    max_uncompressed_bytes: int
    max_compressed_bytes: int
    max_selectors: int
    max_history_limit_per_selector: int
    @classmethod
    def from_dict(cls, data):
        keys = ["max_search_rows","max_offer_rows","max_optional_rows","max_total_rows","max_uncompressed_bytes","max_compressed_bytes","max_selectors","max_history_limit_per_selector"]
        missing = [k for k in keys if k not in data]
        if missing:
            raise SnapshotError("missing safety limit: " + ",".join(missing), EXIT_INVALID)
        vals = {k:int(data[k]) for k in keys}
        if any(v <= 0 for v in vals.values()):
            raise SnapshotError("safety limits must be positive", EXIT_INVALID)
        return cls(**vals)
    def as_dict(self):
        return dict(self.__dict__)

@dataclass(frozen=True)
class TrajectorySelector:
    selector_id: str
    route_type: str
    origin_iata: str
    destination_iata: str
    departure_date: str
    return_date: str | None
    stay_nights: int | None
    history_limit: int
    minimum_history_rows: int
    include_all_linked_offers: bool
    required: bool
    @classmethod
    def from_dict(cls, data, limits):
        required = ["selector_id","route_type","origin_iata","destination_iata","departure_date","return_date","stay_nights","history_limit","minimum_history_rows","include_all_linked_offers","required"]
        missing = [k for k in required if k not in data]
        if missing:
            raise SnapshotError("selector missing fields: " + ",".join(missing), EXIT_INVALID)
        rt, o, d = data["route_type"], data["origin_iata"], data["destination_iata"]
        if rt not in {"oneway","roundtrip"}:
            raise SnapshotError("invalid route_type", EXIT_INVALID)
        if not _IATA_RE.match(o) or not _IATA_RE.match(d) or o == d:
            raise SnapshotError("invalid selector IATA", EXIT_INVALID)
        if not _DATE_RE.match(data["departure_date"]):
            raise SnapshotError("invalid departure_date", EXIT_INVALID)
        ret, stay = data.get("return_date"), data.get("stay_nights")
        if rt == "oneway" and (ret is not None or stay is not None):
            raise SnapshotError("oneway selector cannot include return_date/stay_nights", EXIT_INVALID)
        if rt == "roundtrip" and (ret is None or stay is None or not _DATE_RE.match(str(ret))):
            raise SnapshotError("roundtrip selector requires return_date and stay_nights", EXIT_INVALID)
        hist, minimum = int(data["history_limit"]), int(data["minimum_history_rows"])
        if minimum < 7 or hist < minimum or hist > limits.max_history_limit_per_selector:
            raise SnapshotError("invalid history limit/minimum", EXIT_INVALID)
        sid = str(data["selector_id"])
        if not sid or "*" in sid or " " in sid:
            raise SnapshotError("invalid selector_id", EXIT_INVALID)
        return cls(sid, rt, o, d, data["departure_date"], ret, stay, hist, minimum, bool(data["include_all_linked_offers"]), bool(data["required"]))
    def normalized(self):
        return dict(self.__dict__)

@dataclass(frozen=True)
class CompiledSelection:
    tier: str
    selectors: tuple
    search_sql: str
    search_params: tuple
    offer_sql: str
    offer_params: tuple
    optional_sql: str | None
    optional_params: tuple
    fingerprint: str
    limits: SafetyLimits
    include_route_snapshot: bool
    required_source_columns: dict[str, tuple[str, ...]]

def stable_sha256(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

def load_tier_contract(path=None):
    return read_json(path or (database_root() / "snapshot_tiers.json"))

def _tier_config(tier, contract):
    for item in contract.get("tiers", []):
        if item.get("name") == tier:
            return item
    raise SnapshotError("unknown tier", EXIT_INVALID)

def _compile_from_selectors(tier, selectors, limits, include_route_snapshot, contract_version="inline"):
    search_cols = ", ".join("ranked." + c for c in SOURCE_TABLE_COLUMNS["search_observation"])
    union_parts, params = [], []
    for s in selectors:
        where = ["s.route_type = %s", "s.origin_iata = %s", "s.destination_iata = %s", "s.departure_date = %s"]
        vals = [s.route_type, s.origin_iata, s.destination_iata, s.departure_date]
        if s.return_date is None:
            where.append("s.return_date IS NULL")
        else:
            where.append("s.return_date = %s"); vals.append(s.return_date)
        if s.stay_nights is None:
            where.append("s.stay_nights IS NULL")
        else:
            where.append("s.stay_nights = %s"); vals.append(s.stay_nights)
        union_parts.append(f"SELECT {search_cols}, ranked.selector_id FROM (SELECT s.{', s.'.join(SOURCE_TABLE_COLUMNS['search_observation'])}, %s AS selector_id, ROW_NUMBER() OVER (ORDER BY s.observed_at DESC, s.observation_id DESC) AS selector_rn FROM search_observation s WHERE {' AND '.join(where)}) ranked WHERE ranked.selector_rn <= %s")
        params.extend([s.selector_id, *vals, s.history_limit])
    union_sql = " UNION ALL ".join(union_parts)
    output_cols = ", ".join("deduped." + c for c in SOURCE_TABLE_COLUMNS["search_observation"])
    search_sql = f"SELECT {output_cols} FROM (SELECT unioned.*, ROW_NUMBER() OVER (PARTITION BY unioned.observation_id ORDER BY unioned.observed_at DESC, unioned.observation_id DESC) AS dedupe_rn FROM ({union_sql}) unioned) deduped WHERE deduped.dedupe_rn = 1 ORDER BY deduped.observed_at DESC, deduped.observation_id DESC"
    offer_cols = ", ".join("f." + c for c in SOURCE_TABLE_COLUMNS["flight_offer_observation"])
    offer_sql = f"SELECT {offer_cols} FROM flight_offer_observation f JOIN ({search_sql}) selected_search ON selected_search.observation_id = f.observation_id ORDER BY f.observation_id, f.offer_observation_id"
    optional_sql, optional_params = None, ()
    if include_route_snapshot:
        parts, opt = [], []
        for s in selectors:
            where = ["r.route_type = %s", "r.origin_iata = %s", "r.destination_iata = %s"]
            vals = [s.route_type, s.origin_iata, s.destination_iata]
            if s.stay_nights is None:
                where.append("r.stay_nights IS NULL")
            else:
                where.append("r.stay_nights = %s"); vals.append(s.stay_nights)
            parts.append("(" + " AND ".join(where) + ")"); opt.extend(vals)
        optional_sql = "SELECT " + ", ".join("r." + c for c in SOURCE_TABLE_COLUMNS["service_route_analysis_snapshot"]) + " FROM service_route_analysis_snapshot r WHERE " + " OR ".join(parts) + " ORDER BY generated_at DESC, snapshot_id DESC LIMIT %s"
        opt.append(limits.max_optional_rows); optional_params = tuple(opt)
    fingerprint = stable_sha256({"tier":tier,"schema_version":SCHEMA_VERSION,"selector_contract_version":contract_version,"selectors":[s.normalized() for s in selectors],"limits":limits.as_dict(),"source_commit":"f11e8e8","public_commit":"12f5028","query_compiler_version":QUERY_COMPILER_VERSION})
    required_source_columns = {
        "search_observation": tuple(SOURCE_TABLE_COLUMNS["search_observation"]),
        "flight_offer_observation": tuple(SOURCE_TABLE_COLUMNS["flight_offer_observation"]),
    }
    if include_route_snapshot:
        required_source_columns["service_route_analysis_snapshot"] = tuple(SOURCE_TABLE_COLUMNS["service_route_analysis_snapshot"])
    return CompiledSelection(tier, tuple(selectors), search_sql, tuple(params), offer_sql, tuple(params), optional_sql, optional_params, fingerprint, limits, include_route_snapshot, required_source_columns)

def compile_selection(tier, tier_contract=None):
    contract = load_tier_contract(tier_contract)
    cfg = _tier_config(tier, contract)
    limits = SafetyLimits.from_dict(cfg.get("limits", {}))
    raw = cfg.get("selectors") or []
    if not raw:
        raise SnapshotError("empty selector blocked", EXIT_UNBOUNDED)
    if len(raw) > limits.max_selectors:
        raise SnapshotError("selector count exceeds limit", EXIT_LIMIT)
    selectors = [TrajectorySelector.from_dict(s, limits) for s in raw]
    if len({s.selector_id for s in selectors}) != len(selectors):
        raise SnapshotError("duplicate selector_id", EXIT_INVALID)
    return _compile_from_selectors(tier, selectors, limits, bool(cfg.get("include_route_snapshot")), contract.get("selector_contract_version"))

def compile_selection_for_single(compiled, selector):
    return _compile_from_selectors(compiled.tier, [selector], compiled.limits, False, "single-selector")

async def begin_read_only(conn):
    async with conn.cursor() as cur:
        await cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        await cur.execute("START TRANSACTION READ ONLY")

async def fetch_all(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = []
        while True:
            chunk = await cur.fetchmany(500)
            if not chunk:
                break
            rows.extend(dict(zip(cols, r)) for r in chunk)
        return rows

async def _scalar(conn, sql, params=()):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()
        return int(row[0] or 0)


def required_source_columns_for(compiled: CompiledSelection) -> dict[str, set[str]]:
    return {table: set(columns) for table, columns in compiled.required_source_columns.items()}


async def validate_source_schema(conn, compiled: CompiledSelection):
    required_by_table = required_source_columns_for(compiled)
    missing: list[str] = []
    validated: dict[str, list[str]] = {}
    async with conn.cursor() as cur:
        for table, required in required_by_table.items():
            await cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s",
                (table,),
            )
            found = {str(row[0]) for row in await cur.fetchmany(1000)}
            for column in sorted(required - found):
                missing.append(f"{table}.{column}")
            validated[table] = sorted(required)
    if missing:
        detail = ",".join(missing)
        raise SchemaContractError(f"missing_columns={detail}")
    return validated

async def exact_preflight(conn, compiled):
    selector_results = []
    for s in compiled.selectors:
        c = compile_selection_for_single(compiled, s)
        search_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({c.search_sql}) q", c.search_params)
        offer_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({c.offer_sql}) q", c.offer_params)
        valid_price_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({c.offer_sql}) q WHERE q.price_krw IS NOT NULL AND q.price_krw > 0", c.offer_params)
        return_flight_rows = 0
        if s.route_type == "roundtrip":
            return_flight_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({c.offer_sql}) q WHERE q.ret_flight_number IS NOT NULL AND q.ret_flight_number <> ''", c.offer_params)
        selector_results.append({"selector_id":s.selector_id,"route_type":s.route_type,"search_rows":search_rows,"offer_rows":offer_rows,"valid_price_offer_rows":valid_price_rows,"return_flight_offer_rows":return_flight_rows,"minimum_history_rows":s.minimum_history_rows,"history_pass":search_rows >= s.minimum_history_rows,"valid_price_pass":valid_price_rows > 0,"return_flight_pass":True if s.route_type == "oneway" else return_flight_rows > 0})
    search_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({compiled.search_sql}) q", compiled.search_params)
    offer_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({compiled.offer_sql}) q", compiled.offer_params)
    optional_rows = 0
    if compiled.optional_sql:
        optional_rows = await _scalar(conn, f"SELECT COUNT(*) FROM ({compiled.optional_sql}) q", compiled.optional_params)
    total_rows = search_rows + offer_rows + optional_rows
    limits = compiled.limits
    checks = {"search_rows":{"actual":search_rows,"max":limits.max_search_rows,"pass":search_rows <= limits.max_search_rows},"offer_rows":{"actual":offer_rows,"max":limits.max_offer_rows,"pass":offer_rows <= limits.max_offer_rows},"optional_rows":{"actual":optional_rows,"max":limits.max_optional_rows,"pass":optional_rows <= limits.max_optional_rows},"total_rows":{"actual":total_rows,"max":limits.max_total_rows,"pass":total_rows <= limits.max_total_rows}}
    coverage_pass = all(r["history_pass"] and r["valid_price_pass"] and r["return_flight_pass"] for r in selector_results)
    limits_pass = all(v["pass"] for v in checks.values())
    return {"status":"preflight_pass" if coverage_pass and limits_pass else "preflight_fail","tier":compiled.tier,"selection_fingerprint":compiled.fingerprint,"selector_count":len(compiled.selectors),"selectors":selector_results,"search_rows":search_rows,"offer_rows":offer_rows,"optional_rows":optional_rows,"total_rows":total_rows,"limits":checks,"coverage_pass":coverage_pass,"limits_pass":limits_pass,"query_compiler_version":QUERY_COMPILER_VERSION,"read_only_transaction":"START TRANSACTION READ ONLY","error_code":0 if coverage_pass and limits_pass else EXIT_COVERAGE}

def enforce_preflight(preflight):
    if not preflight.get("coverage_pass"):
        raise SnapshotError("selector coverage/history gate failed", EXIT_COVERAGE)
    if not preflight.get("limits_pass"):
        raise SnapshotError("safety limit exceeded", EXIT_LIMIT)

# C4.1H portable JSON default override
from datetime import timedelta as _timedelta

def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, _timedelta):
        total = int(value.total_seconds())
        sign = '-' if total < 0 else ''
        total = abs(total)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
