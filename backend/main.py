from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import aiomysql
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.db import close_pool, create_pool, get_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await create_pool()
    worker_task: asyncio.Task | None = None
    try:
        from recommend.job_worker import background_worker_loop

        worker_task = asyncio.create_task(background_worker_loop())
        logger.info("background worker task created")
    except Exception:
        logger.exception("Failed to start background worker")

    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        await close_pool()


app = FastAPI(
    title="BARO API",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        return {"status": "unavailable"}

    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) AS count FROM search_observation;"
                )
                row = await cursor.fetchone()
    except Exception:
        logger.exception("DB health query failed")
        return {"status": "error", "detail": "db query failed"}

    return {
        "status": "ok",
        "search_observation_count": int(row["count"] if row else 0),
    }


@app.get("/health/model")
async def health_model() -> dict[str, Any]:
    from ml_inference.model_status import check_model_status

    return check_model_status()


try:
    from flights.router import router as flights_router

    app.include_router(flights_router, prefix="/flights")
except ImportError:
    # Phase 3-1 keeps health endpoints available if crawler dependencies are absent.
    # app.include_router(flights_router, prefix="/flights")
    pass

try:
    from recommend.router import router as recommend_router

    app.include_router(recommend_router, prefix="/recommend")
except ImportError:
    # Keep existing health/search endpoints available if model dependencies are absent.
    # app.include_router(recommend_router, prefix="/recommend")
    pass

try:
    from auth.router import router as auth_router

    app.include_router(auth_router, prefix="/auth")
except ImportError:
    # Phase 1 keeps /health available even if optional auth imports are not ready.
    # app.include_router(auth_router, prefix="/auth")
    pass

try:
    from users.router import router as users_router

    app.include_router(users_router, prefix="/users")
except ImportError:
    # Phase 1 keeps /health available even if optional users imports are not ready.
    # app.include_router(users_router, prefix="/users")
    pass
