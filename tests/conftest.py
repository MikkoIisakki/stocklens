"""Shared pytest fixtures for unit and integration tests."""

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Session-scoped connection pool pointed at the test database.

    Requires DATABASE_URL env var (set by CI and by local .env when running
    tests outside Docker).  Applies all migrations once per session.
    """
    database_url = os.environ["DATABASE_URL"]
    pool: asyncpg.Pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)

    # Apply all migrations in lexical order so tests have a real schema
    async with pool.acquire() as conn:
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = migration.read_text()
            await conn.execute(sql)

    yield pool
    await pool.close()


@pytest_asyncio.fixture(loop_scope="session")
async def db_conn(db_pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.Connection, None]:
    """Per-test connection wrapped in a rolled-back transaction.

    Each test gets a clean slate without truncating tables, keeping tests fast
    and fully isolated from each other.
    """
    async with db_pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        yield conn
        await tr.rollback()
