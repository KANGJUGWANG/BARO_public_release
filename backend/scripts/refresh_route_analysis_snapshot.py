"""Refresh route analysis snapshots for the MVP 8 routes.

Usage:
    cd ~/BARO/backend
    source .venv/bin/activate
    python -m scripts.refresh_route_analysis_snapshot

Requires the migration table and writer DB credentials.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

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


async def main() -> None:
    try:
        logger.info("route analysis snapshot refresh started")
        await create_pool()

        pool = get_pool()
        writer_pool = get_writer_pool()
        if pool is None:
            logger.error("DB pool unavailable. Check .env.backend settings.")
            return
        if writer_pool is None:
            logger.error("Writer pool unavailable. Check DB_WRITER_USER/DB_WRITER_PASSWORD.")
            return

        results = []
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                for spec in MVP_ROUTES:
                    route_label = f"{spec['route_type']}:{spec['origin']}:{spec['destination']}:{spec.get('stay_nights')}"
                    logger.info("computing analysis: %s", route_label)
                    try:
                        data = await compute_route_analysis(cur, spec)
                        results.append(data)
                        logger.info(
                            "  status=%s obs=%s offers=%s",
                            data.get("status"),
                            data.get("observation_count"),
                            data.get("valid_offer_count"),
                        )
                    except Exception as exc:  # noqa: BLE001 - continue other routes.
                        logger.warning("  failed: %s", exc.__class__.__name__)

        success_count = 0
        for data in results:
            if await upsert_route_analysis_snapshot(writer_pool, data):
                success_count += 1
                logger.info("upserted: %s", data["route_key"])
            else:
                logger.warning("upsert failed: %s", data.get("route_key"))

        logger.info("done: %d/%d routes upserted", success_count, len(results))
    finally:
        try:
            await close_pool()
        except Exception as exc:  # noqa: BLE001 - cleanup must not mask the script result.
            logger.debug("pool cleanup warning: %s", exc.__class__.__name__)


if __name__ == "__main__":
    asyncio.run(main())
