#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import shutil
import time
from pathlib import Path
from db_snapshot_common import (
    EXIT_SUCCESS, EXIT_LIMIT, TABLES, SchemaContractError, SnapshotError, begin_read_only, compile_selection,
    connect_from_env, database_root, enforce_preflight, exact_preflight, json_default, validate_source_schema,
    print_result, sanitize_row, sha256_file, snapshot_manifest, verify_snapshot, write_json,
)


def _write_row(gz, row: dict) -> int:
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True, default=json_default, separators=(",", ":")) + "\n").encode("utf-8")
    gz.write(data)
    return len(data)


async def stream_table(conn, sql: str, params: tuple, table: str, path: Path, row_limit: int, byte_limit: int, selected_ids: set | None = None) -> tuple[int, int]:
    count = 0
    uncompressed = 0
    with gzip.GzipFile(filename="", mode="wb", fileobj=path.open("wb"), mtime=0) as gz:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            while True:
                chunk = await cur.fetchmany(500)
                if not chunk:
                    break
                for values in chunk:
                    row = dict(zip(cols, values))
                    if selected_ids is not None and table == "search_observation":
                        selected_ids.add(row["observation_id"])
                    if selected_ids is not None and table == "flight_offer_observation" and row["observation_id"] not in selected_ids:
                        raise SnapshotError("orphan offer during export", 9)
                    uncompressed += _write_row(gz, sanitize_row(table, row))
                    count += 1
                    if count > row_limit or uncompressed > byte_limit:
                        raise SnapshotError(f"runtime limit exceeded for {table}", EXIT_LIMIT)
    if path.stat().st_size > byte_limit:
        raise SnapshotError(f"compressed byte limit exceeded for {table}", EXIT_LIMIT)
    return count, uncompressed


async def export_async(args) -> int:
    compiled = compile_selection(args.tier, args.tier_contract)
    conn = await connect_from_env("BARO_EXPORT_DB", args.db_driver)
    try:
        await begin_read_only(conn)
        schema_check = await validate_source_schema(conn, compiled)
        preflight = await exact_preflight(conn, compiled)
        if args.plan:
            print_result({"snapshot_export": "PLAN", **preflight}, args.json_output, args.quiet)
            return EXIT_SUCCESS if preflight["status"] == "preflight_pass" else preflight.get("error_code", 11)
        enforce_preflight(preflight)
        output = args.output.resolve()
        if output.exists() and not args.replace:
            raise SnapshotError("output exists; use --replace", 7)
        partial = output.parent / ".partial" / f"{args.snapshot_version}-{int(time.time())}"
        if partial.exists():
            shutil.rmtree(partial)
        partial.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_root() / "schema.sql", partial / "schema.sql")
        files = []
        tables = []
        selected_ids: set = set()
        path = partial / "search_observation.jsonl.gz"
        count, uncomp = await stream_table(conn, compiled.search_sql, compiled.search_params, "search_observation", path, compiled.limits.max_search_rows, compiled.limits.max_uncompressed_bytes, selected_ids)
        files.append({"relative_path": path.name, "table": "search_observation", "sha256": sha256_file(path), "size_bytes": path.stat().st_size, "uncompressed_bytes": uncomp, "row_count": count, "media_type": "application/jsonl+gzip", "required": True})
        tables.append({"name": "search_observation", "required": True, "row_count": count, "pk": "observation_id", "source_filter": "bounded tier selector", "sanitization_rules": {"search_url": "redacted", "raw_file_path": "null"}, "output_file": path.name})
        path = partial / "flight_offer_observation.jsonl.gz"
        count, uncomp = await stream_table(conn, compiled.offer_sql, compiled.offer_params, "flight_offer_observation", path, compiled.limits.max_offer_rows, compiled.limits.max_uncompressed_bytes, selected_ids)
        files.append({"relative_path": path.name, "table": "flight_offer_observation", "sha256": sha256_file(path), "size_bytes": path.stat().st_size, "uncompressed_bytes": uncomp, "row_count": count, "media_type": "application/jsonl+gzip", "required": True})
        tables.append({"name": "flight_offer_observation", "required": True, "row_count": count, "pk": "offer_observation_id", "source_filter": "join to selected observations", "sanitization_rules": {"seller_domain": "null"}, "output_file": path.name})
        if compiled.optional_sql:
            path = partial / "service_route_analysis_snapshot.jsonl.gz"
            count, uncomp = await stream_table(conn, compiled.optional_sql, compiled.optional_params, "service_route_analysis_snapshot", path, compiled.limits.max_optional_rows, compiled.limits.max_uncompressed_bytes)
            if count:
                files.append({"relative_path": path.name, "table": "service_route_analysis_snapshot", "sha256": sha256_file(path), "size_bytes": path.stat().st_size, "uncompressed_bytes": uncomp, "row_count": count, "media_type": "application/jsonl+gzip", "required": False})
                tables.append({"name": "service_route_analysis_snapshot", "required": False, "row_count": count, "pk": "snapshot_id", "source_filter": "bounded selected routes", "sanitization_rules": {"seller_domain": "null"}, "output_file": path.name})
            else:
                path.unlink(missing_ok=True)
        total_rows = sum(t["row_count"] for t in tables)
        total_uncompressed = sum(f["uncompressed_bytes"] for f in files)
        total_compressed = sum(f["size_bytes"] for f in files)
        if total_rows > compiled.limits.max_total_rows or total_uncompressed > compiled.limits.max_uncompressed_bytes or total_compressed > compiled.limits.max_compressed_bytes:
            raise SnapshotError("runtime aggregate safety limit exceeded", EXIT_LIMIT)
        manifest = snapshot_manifest(args.tier, args.snapshot_version, files, tables, {"policy": "bounded_tier_selector", "private_source_identifier": None, "selection_fingerprint": compiled.fingerprint, "selector_ids": [s.selector_id for s in compiled.selectors], "exact_preflight": preflight, "safety_limits": compiled.limits.as_dict(), "query_compiler_version": "bounded-selector-v1", "read_only_transaction": "START TRANSACTION READ ONLY", "schema_compatibility": schema_check})
        write_json(partial / "snapshot_manifest.json", manifest)
        verify_snapshot(partial, tier=args.tier, strict=True, deep=True)
        if output.exists():
            shutil.rmtree(output)
        partial.replace(output)
        print_result({"snapshot_export": "PASS", "tier": args.tier, "output": output.name, "selection_fingerprint": compiled.fingerprint, "tables": len(tables), "total_rows": manifest["total_rows"], "error_code": 0}, args.json_output, args.quiet)
        return EXIT_SUCCESS
    finally:
        try:
            await conn.rollback()
        finally:
            conn.close()



def classify_db_error(exc: Exception) -> dict:
    args = getattr(exc, "args", ())
    number = args[0] if args and isinstance(args[0], int) else None
    message = str(args[1] if len(args) > 1 else exc)
    payload = {
        "snapshot_export": "FAIL",
        "error_code": "database_query_contract_error",
        "exit_status": 6,
        "db_error_number": number,
        "error_type": "database_error",
    }
    if number == 1054:
        payload["error_type"] = "unknown_column"
        import re
        match = re.search(r"Unknown column '([^']+)'", message)
        if match:
            raw = match.group(1)
            prefix_map = {"f.": "flight_offer_observation.", "s.": "search_observation.", "r.": "service_route_analysis_snapshot."}
            identifier = raw
            for prefix, table_prefix in prefix_map.items():
                if raw.startswith(prefix):
                    identifier = table_prefix + raw[len(prefix):]
                    break
            payload["identifier"] = identifier
    return payload

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tier", default="minimal-repro")
    p.add_argument("--tier-contract", type=Path, default=None)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--snapshot-version", default="synthetic-c4")
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--replace", action="store_true")
    p.add_argument("--db-driver", choices=["auto", "aiomysql", "pymysql"], default="auto")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    try:
        return asyncio.run(export_async(args))
    except SchemaContractError as exc:
        print_result({"snapshot_export": "FAIL", "error_code": exc.public_code, "exit_status": exc.exit_code, "message": str(exc)}, args.json_output)
        return exc.exit_code
    except SnapshotError as exc:
        print_result({"snapshot_export": "FAIL", "error_code": exc.exit_code, "message": str(exc)}, args.json_output)
        return exc.exit_code
    except Exception as exc:
        payload = classify_db_error(exc)
        print_result(payload, args.json_output)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
