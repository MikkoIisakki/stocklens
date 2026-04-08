"""FastAPI dependencies shared across routers.

The asyncpg pool is created once at application startup and injected into
request handlers via Depends(get_pool). This avoids per-request connection
overhead and keeps handlers free of setup boilerplate.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Any

import asyncpg
from fastapi import Depends, Request

if TYPE_CHECKING:
    _PoolType = asyncpg.Pool[asyncpg.Record]
else:
    _PoolType = asyncpg.Pool


async def get_pool(request: Request) -> AsyncGenerator[Any, None]:
    """Yield the shared asyncpg pool stored on app.state."""
    yield request.app.state.pool


Pool = Annotated[_PoolType, Depends(get_pool)]
