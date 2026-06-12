#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from db_snapshot_common import SnapshotError, connect_from_env, database_root, iter_jsonl_gz, print_result, sha256_file, verify_snapshot


async def exec_sql(conn, sql: str) -> None:
    cleaned = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    async with conn.cursor() as cur:
        for stmt in [s.strip() for s in cleaned.split(";") if s.strip()]:
            await cur.execute(stmt)


async def table_count(conn, table: str) -> int:
    async with conn.cursor() as cur:
        await cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cur.fetchone()
        return int(row[0])


async def connect_with_retry(seconds: int):
    deadline = asyncio.get_running_loop().time() + max(1, seconds)
    last_exc = None
    while True:
        try:
            return await connect_from_env("DB")
        except Exception as exc:
            last_exc = exc
            if asyncio.get_running_loop().time() >= deadline:
                raise last_exc
            await asyncio.sleep(2)


async def restore_async(args) -> int:
    result = verify_snapshot(args.snapshot_root, tier=None, strict=True, deep=True)
    manifest = result["manifest"]
    conn = await connect_with_retry(args.db_wait_seconds)
    imported = 0
    try:
        existing = 0
        for table in ["search_observation", "flight_offer_observation"]:
            try:
                existing += await table_count(conn, table)
            except Exception:
                pass
        if existing and not args.allow_existing_same_snapshot:
            raise SnapshotError("target database is not empty", 7)
        schema = (database_root() / "schema.sql").read_text(encoding="utf-8")
        await exec_sql(conn, schema)
        for file_info in manifest["files"]:
            table = file_info["table"]
            rows = list(iter_jsonl_gz(args.snapshot_root / file_info["relative_path"]))
            if not rows:
                continue
            cols = list(rows[0].keys())
            placeholders = ",".join(["%s"] * len(cols))
            sql = f"INSERT IGNORE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
            async with conn.cursor() as cur:
                for row in rows:
                    await cur.execute(sql, tuple(row.get(c) for c in cols))
                    imported += 1
        state_sql = "INSERT IGNORE INTO baro_reproduction_state (schema_version, snapshot_version, snapshot_manifest_sha256, tier, status, started_at, completed_at, imported_rows, tool_version) VALUES (%s,%s,%s,%s,%s,NOW(),NOW(),%s,%s)"
        async with conn.cursor() as cur:
            await cur.execute(state_sql, (manifest["schema_version"], manifest["snapshot_version"], sha256_file(args.snapshot_root / "snapshot_manifest.json"), manifest["tier"], "completed", imported, "phase3.6-c4"))
        await conn.commit()
        print_result({"snapshot_restore": "PASS", "imported_rows": imported, "snapshot_version": manifest["snapshot_version"], "error_code": 0}, args.json_output, args.quiet)
        return 0
    except Exception:
        await conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot-root", type=Path, required=True)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--replace-empty-only", action="store_true")
    p.add_argument("--allow-existing-same-snapshot", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--db-wait-seconds", type=int, default=60)
    args = p.parse_args()
    try:
        return asyncio.run(restore_async(args))
    except SnapshotError as exc:
        print_result({"snapshot_restore": "FAIL", "error_code": exc.exit_code, "message": str(exc)}, args.json_output)
        return exc.exit_code
    except Exception as exc:
        message = f"{exc.__class__.__name__}: {str(exc)}"
        print_result({"snapshot_restore": "FAIL", "error_code": 8, "message": message}, args.json_output)
        return 8


if __name__ == "__main__":
    raise SystemExit(main())
