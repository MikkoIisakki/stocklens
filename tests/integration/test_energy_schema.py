"""Integration tests for the energy schema (migrations 002 + 004).

Verifies the energy_region and energy_price tables exist with the expected
constraints (interval-based per ADR-005), and that ingest_run accepts
market='ENERGY'. Requires a running database (DATABASE_URL env var).

Each test creates its own direct asyncpg connection to avoid event-loop
scope conflicts between the session-scoped pool and function-scoped tests.
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio


@pytest_asyncio.fixture(loop_scope="function")
async def conn(db_pool: asyncpg.Pool) -> asyncpg.Connection:
    """Fresh asyncpg connection per test using the function event loop.

    Depends on db_pool to guarantee migrations + seeds are applied before
    any test in this module runs.
    """
    database_url = os.environ["DATABASE_URL"]
    c = await asyncpg.connect(database_url)
    yield c
    await c.close()


def _slot(year: int, month: int, day: int, hour: int = 14) -> tuple[datetime, datetime]:
    start = datetime(year, month, day, hour, 0, tzinfo=UTC)
    return start, start + timedelta(hours=1)


@pytest.mark.asyncio
async def test_energy_region_fi_seeded(conn: asyncpg.Connection) -> None:
    """FI region must exist after seed with correct VAT and electricity tax."""
    row = await conn.fetchrow(
        "SELECT vat_rate, electricity_tax_c_kwh, active FROM energy_region WHERE code = 'FI'"
    )
    assert row is not None, "FI region missing — seed 002 not applied"
    assert Decimal(str(row["vat_rate"])) == Decimal("0.2550")
    assert Decimal(str(row["electricity_tax_c_kwh"])) == Decimal("2.2400")
    assert row["active"] is True


@pytest.mark.asyncio
async def test_energy_region_all_codes_seeded(conn: asyncpg.Connection) -> None:
    """All six ENTSO-E bidding zones must be seeded."""
    rows = await conn.fetch("SELECT code FROM energy_region ORDER BY code")
    codes = {r["code"] for r in rows}
    assert codes == {"EE", "FI", "LT", "LV", "SE3", "SE4"}


@pytest.mark.asyncio
async def test_energy_price_insert_and_retrieve(conn: asyncpg.Connection) -> None:
    """A valid interval price row can be inserted and retrieved."""
    start, end = _slot(2025, 1, 15, hour=14)
    try:
        await conn.execute(
            """
            INSERT INTO energy_price
                (region_code, interval_start, interval_end, interval_minutes,
                 price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, $2, 60, 85.50, 8.55, 13.48)
            ON CONFLICT DO NOTHING
            """,
            start,
            end,
        )
        row = await conn.fetchrow(
            """
            SELECT price_eur_mwh, spot_c_kwh, total_c_kwh, interval_minutes
              FROM energy_price
             WHERE region_code='FI' AND interval_start=$1
            """,
            start,
        )
        assert row is not None
        assert Decimal(str(row["price_eur_mwh"])) == Decimal("85.5000")
        assert Decimal(str(row["spot_c_kwh"])) == Decimal("8.5500")
        assert Decimal(str(row["total_c_kwh"])) == Decimal("13.4800")
        assert row["interval_minutes"] == 60
    finally:
        await conn.execute(
            "DELETE FROM energy_price WHERE region_code='FI' AND interval_start=$1",
            start,
        )


@pytest.mark.asyncio
async def test_energy_price_negative_price_allowed(conn: asyncpg.Connection) -> None:
    """ENTSO-E prices can go negative — must be stored without error."""
    start, end = _slot(2025, 1, 18, hour=3)
    try:
        await conn.execute(
            """
            INSERT INTO energy_price
                (region_code, interval_start, interval_end, interval_minutes,
                 price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, $2, 60, -12.00, -1.20, 1.28)
            ON CONFLICT DO NOTHING
            """,
            start,
            end,
        )
        row = await conn.fetchrow(
            "SELECT price_eur_mwh FROM energy_price WHERE region_code='FI' AND interval_start=$1",
            start,
        )
        assert row is not None
        assert Decimal(str(row["price_eur_mwh"])) == Decimal("-12.0000")
    finally:
        await conn.execute(
            "DELETE FROM energy_price WHERE region_code='FI' AND interval_start=$1",
            start,
        )


@pytest.mark.asyncio
async def test_energy_price_unique_constraint(conn: asyncpg.Connection) -> None:
    """Inserting a duplicate (region, interval_start) must raise UniqueViolationError."""
    start, end = _slot(2025, 1, 16, hour=10)
    try:
        await conn.execute(
            """
            INSERT INTO energy_price
                (region_code, interval_start, interval_end, interval_minutes,
                 price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, $2, 60, 70.00, 7.00, 11.70)
            ON CONFLICT DO NOTHING
            """,
            start,
            end,
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO energy_price
                    (region_code, interval_start, interval_end, interval_minutes,
                     price_eur_mwh, spot_c_kwh, total_c_kwh)
                VALUES ('FI', $1, $2, 60, 72.00, 7.20, 11.90)
                """,
                start,
                end,
            )
    finally:
        await conn.execute(
            "DELETE FROM energy_price WHERE region_code='FI' AND interval_start=$1",
            start,
        )


@pytest.mark.asyncio
async def test_energy_price_interval_minutes_must_be_positive(conn: asyncpg.Connection) -> None:
    """Zero or negative interval_minutes is rejected by the check constraint."""
    start, end = _slot(2025, 1, 17, hour=5)
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO energy_price
                (region_code, interval_start, interval_end, interval_minutes,
                 price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, $2, 0, 70.00, 7.00, 11.70)
            """,
            start,
            end,
        )


@pytest.mark.asyncio
async def test_energy_price_interval_end_after_start(conn: asyncpg.Connection) -> None:
    """interval_end must be strictly after interval_start (chronology check)."""
    start, _ = _slot(2025, 1, 17, hour=6)
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO energy_price
                (region_code, interval_start, interval_end, interval_minutes,
                 price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, $1, 60, 70.00, 7.00, 11.70)
            """,
            start,
        )


@pytest.mark.asyncio
async def test_ingest_run_accepts_energy_market(conn: asyncpg.Connection) -> None:
    """ingest_run must accept market='ENERGY' after migration 002."""
    row_id: int = await conn.fetchval(
        "INSERT INTO ingest_run (status, market) VALUES ('running', 'ENERGY') RETURNING id"
    )
    row = await conn.fetchrow("SELECT market FROM ingest_run WHERE id = $1", row_id)
    assert row is not None
    assert row["market"] == "ENERGY"
    await conn.execute("DELETE FROM ingest_run WHERE id = $1", row_id)
