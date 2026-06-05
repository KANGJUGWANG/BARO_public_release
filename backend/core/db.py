from __future__ import annotations

import logging

import aiomysql

from core.config import settings

logger = logging.getLogger(__name__)

_pool: aiomysql.Pool | None = None
_writer_pool: aiomysql.Pool | None = None


async def create_pool() -> None:
    global _pool, _writer_pool

    if _pool is None:
        if not all(
            [
                settings.db_host,
                settings.db_name,
                settings.db_user,
                settings.db_password,
            ]
        ):
            logger.warning("DB pool unavailable: missing DB environment variables")
        else:
            try:
                _pool = await aiomysql.create_pool(
                    host=settings.db_host,
                    port=settings.db_port,
                    db=settings.db_name,
                    user=settings.db_user,
                    password=settings.db_password,
                    autocommit=True,
                    charset="utf8mb4",
                    connect_timeout=5,
                    minsize=1,
                    maxsize=3,
                )
            except Exception as exc:
                _pool = None
                logger.warning("DB pool unavailable: %s", exc.__class__.__name__)

    if _writer_pool is None:
        if not all(
            [
                settings.db_writer_host or settings.db_host,
                settings.db_name,
                settings.db_writer_user,
                settings.db_writer_password,
            ]
        ):
            logger.info("DB writer pool unavailable: missing writer environment variables")
        else:
            try:
                _writer_pool = await aiomysql.create_pool(
                    host=settings.db_writer_host or settings.db_host,
                    port=settings.db_writer_port,
                    db=settings.db_name,
                    user=settings.db_writer_user,
                    password=settings.db_writer_password,
                    autocommit=True,
                    charset="utf8mb4",
                    connect_timeout=5,
                    minsize=1,
                    maxsize=2,
                )
            except Exception as exc:
                _writer_pool = None
                logger.warning("DB writer pool unavailable: %s", exc.__class__.__name__)


async def close_pool() -> None:
    global _pool, _writer_pool

    if _writer_pool is not None:
        _writer_pool.close()
        await _writer_pool.wait_closed()
        _writer_pool = None

    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


def get_pool() -> aiomysql.Pool | None:
    return _pool


def get_writer_pool() -> aiomysql.Pool | None:
    return _writer_pool
