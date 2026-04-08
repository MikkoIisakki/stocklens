"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from app.api.routers import assets, health
from app.common.config import settings
from app.common.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create the asyncpg pool on startup; close it on shutdown."""
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
    if pool is None:
        raise RuntimeError("asyncpg.create_pool returned None")
    app.state.pool = pool
    yield
    await app.state.pool.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Recommendator",
        description="Stock recommendation system for US and Finnish markets.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(assets.router)

    return app


app = create_app()
