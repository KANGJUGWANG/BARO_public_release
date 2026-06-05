#!/usr/bin/env python3
"""Refresh route analysis snapshots only when source observations advanced.

Usage:
    cd ~/BARO/backend
    source .venv/bin/activate
    python -m scripts.refresh_route_analysis_snapshot_if_needed [--force] [--trigger pipeline|manual|timer]

Exit codes:
    0: refreshed, partially refreshed, or skipped
    1: failed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(".env.backend")

from core.db import close_pool, create_pool, get_pool, get_writer_pool  # noqa: E402
from recommend.route_analysis import (  # noqa: E402
    MVP_ROUTES,
    compute_route_analysis,
    upsert_route_analysis_snapshot,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LOCK_FILE = "/tmp/baro_route_analysis_snapshot.lock"


async def _get_latest_source_observed_at(pool: Any) -> datetime | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT MAX(observed_at)
                FROM search_observation
                WHERE crawl_status = 'success'
                  AND route_type IN ('oneway', 'roundtrip')
                """
            )
            row = await cur.fetchone()
            return row[0] if row else None


async def _get_latest_snapshot_source_observed_at(pool: Any) -> datetime | None:
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT MAX(source_latest_observed_at)
                    FROM service_route_analysis_snapshot
                    """
                )
                row = await cur.fetchone()
                return row[0] if row else None
    except Exception as exc:  # noqa: BLE001 - table missing should trigger refresh.
        logger.info("snapshot table check: %s (will refresh)", exc.__class__.__name__)
        return None


async def run(force: bool, trigger: str) -> dict[str, Any]:
    await create_pool()
    try:
        pool = get_pool()
        writer_pool = get_writer_pool()

        if pool is None:
            return {"status": "failed", "reason": "db_pool_unavailable", "trigger": trigger}
        if writer_pool is None:
            return {"status": "failed", "reason": "writer_pool_unavailable", "trigger": trigger}

        latest_source = await _get_latest_source_observed_at(pool)
        latest_snapshot = await _get_latest_snapshot_source_observed_at(pool)

        logger.info("latest_source_observed_at: %s", latest_source)
        logger.info("latest_snapshot_source_observed_at: %s", latest_snapshot)

        should_refresh = (
            force
            or latest_snapshot is None
            or (latest_source is not None and latest_source > latest_snapshot)
        )
        if not should_refresh:
            logger.info("status=skipped reason=no_new_data trigger=%s", trigger)
            return {
                "status": "skipped",
                "reason": "no_new_data",
                "trigger": trigger,
                "latest_source_observed_at": str(latest_source),
                "latest_snapshot_source_observed_at": str(latest_snapshot),
            }

        logger.info("status=refreshing trigger=%s force=%s", trigger, force)
        t0 = time.perf_counter()
        results: list[dict[str, Any]] = []

        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for spec in MVP_ROUTES:
                        route_label = f"{spec['route_type']}:{spec['origin']}:{spec['destination']}:{spec.get('stay_nights')}"
                        try:
                            data = await compute_route_analysis(cur, spec)
                            results.append(data)
                            logger.info(
                                "  computed: %s status=%s obs=%s",
                                route_label,
                                data.get("status"),
                                data.get("observation_count"),
                            )
                        except Exception as exc:  # noqa: BLE001 - continue remaining routes.
                            logger.warning("  compute failed: %s %s", route_label, exc.__class__.__name__)

            upserted = 0
            for data in results:
                if await upsert_route_analysis_snapshot(writer_pool, data):
                    upserted += 1
                    logger.info("  upserted: %s", data["route_key"])
                else:
                    logger.warning("  upsert failed: %s", data.get("route_key"))

            elapsed = time.perf_counter() - t0
            if upserted == len(MVP_ROUTES):
                status = "refreshed"
                exit_reason = None
            elif upserted > 0:
                status = "partial_refreshed"
                exit_reason = "partial_upsert"
            else:
                status = "failed"
                exit_reason = "no_routes_upserted"

            logger.info(
                "status=%s upserted=%d/%d elapsed=%.1fs trigger=%s",
                status,
                upserted,
                len(MVP_ROUTES),
                elapsed,
                trigger,
            )
            return {
                "status": status,
                "reason": exit_reason,
                "upserted": upserted,
                "total": len(MVP_ROUTES),
                "elapsed_seconds": round(elapsed, 1),
                "trigger": trigger,
                "latest_source_observed_at": str(latest_source),
                "latest_snapshot_source_observed_at": str(latest_snapshot),
            }
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            logger.error("status=failed reason=%s elapsed=%.1fs", exc.__class__.__name__, elapsed)
            return {
                "status": "failed",
                "reason": exc.__class__.__name__,
                "elapsed_seconds": round(elapsed, 1),
                "trigger": trigger,
            }
    finally:
        try:
            await close_pool()
        except Exception as exc:  # noqa: BLE001 - cleanup warning only.
            logger.debug("pool cleanup warning: %s", exc.__class__.__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--trigger", default="manual", choices=["pipeline", "manual", "timer"])
    args = parser.parse_args()

    import fcntl

    lock_fd = open(LOCK_FILE, "w", encoding="utf-8")
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info("status=skipped reason=already_running trigger=%s", args.trigger)
            return 0

        result = asyncio.run(run(force=args.force, trigger=args.trigger))
        return 1 if result.get("status") == "failed" else 0
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:  # noqa: BLE001
            pass
        lock_fd.close()
        try:
            os.unlink(LOCK_FILE)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    sys.exit(main())
