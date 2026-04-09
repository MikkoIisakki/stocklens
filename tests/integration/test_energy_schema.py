"""Integration tests for the energy schema (migration 002).

Verifies that the energy_region and energy_price tables exist with the
expected constraints, and that ingest_run accepts market='ENERGY'.
Requires a running database (DATABASE_URL env var).

Each test creates its own direct asyncpg connection to avoid event-loop
scope conflicts between the session-scoped pool and function-scoped tests.
"""

import os
from datetime import date
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio


@pytest_asyncio.fixture(loop_scope="function")
async def conn() -> asyncpg.Connection:
    """Fresh asyncpg connection per test using the function event loop."""
    database_url = os.environ["DATABASE_URL"]
    c = await asyncpg.connect(database_url)
    yield c
    await c.close()


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
    """All six Nordpool regions must be seeded."""
    rows = await conn.fetch("SELECT code FROM energy_region ORDER BY code")
    codes = {r["code"] for r in rows}
    assert codes == {"EE", "FI", "LT", "LV", "SE3", "SE4"}


@pytest.mark.asyncio
async def test_energy_price_insert_and_retrieve(conn: asyncpg.Connection) -> None:
    """A valid hourly price row can be inserted and retrieved."""
    try:
        await conn.execute(
            """
            INSERT INTO energy_price (region_code, price_date, hour, price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, 14, 85.50, 8.55, 13.48)
            ON CONFLICT DO NOTHING
            """,
            date(2025, 1, 15),
        )
        row = await conn.fetchrow(
            "SELECT price_eur_mwh, spot_c_kwh, total_c_kwh FROM energy_price WHERE region_code='FI' AND price_date=$1 AND hour=14",
            date(2025, 1, 15),
        )
        assert row is not None
        assert Decimal(str(row["price_eur_mwh"])) == Decimal("85.5000")
        assert Decimal(str(row["spot_c_kwh"])) == Decimal("8.5500")
        assert Decimal(str(row["total_c_kwh"])) == Decimal("13.4800")
    finally:
        await conn.execute(
            "DELETE FROM energy_price WHERE region_code='FI' AND price_date=$1 AND hour=14",
            date(2025, 1, 15),
        )


@pytest.mark.asyncio
async def test_energy_price_negative_price_allowed(conn: asyncpg.Connection) -> None:
    """Nordpool prices can go negative — must be stored without error."""
    try:
        await conn.execute(
            """
            INSERT INTO energy_price (region_code, price_date, hour, price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, 3, -12.00, -1.20, 1.28)
            ON CONFLICT DO NOTHING
            """,
            date(2025, 1, 18),
        )
        row = await conn.fetchrow(
            "SELECT price_eur_mwh FROM energy_price WHERE region_code='FI' AND price_date=$1 AND hour=3",
            date(2025, 1, 18),
        )
        assert row is not None
        assert Decimal(str(row["price_eur_mwh"])) == Decimal("-12.0000")
    finally:
        await conn.execute(
            "DELETE FROM energy_price WHERE region_code='FI' AND price_date=$1 AND hour=3",
            date(2025, 1, 18),
        )


@pytest.mark.asyncio
async def test_energy_price_unique_constraint(conn: asyncpg.Connection) -> None:
    """Inserting duplicate (region, date, hour) must raise UniqueViolationError."""
    try:
        await conn.execute(
            """
            INSERT INTO energy_price (region_code, price_date, hour, price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, 10, 70.00, 7.00, 11.70)
            ON CONFLICT DO NOTHING
            """,
            date(2025, 1, 16),
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO energy_price (region_code, price_date, hour, price_eur_mwh, spot_c_kwh, total_c_kwh)
                VALUES ('FI', $1, 10, 72.00, 7.20, 11.90)
                """,
                date(2025, 1, 16),
            )
    finally:
        await conn.execute(
            "DELETE FROM energy_price WHERE region_code='FI' AND price_date=$1 AND hour=10",
            date(2025, 1, 16),
        )


@pytest.mark.asyncio
async def test_energy_price_hour_out_of_range(conn: asyncpg.Connection) -> None:
    """Hour values outside 0-23 must be rejected by the check constraint."""
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO energy_price (region_code, price_date, hour, price_eur_mwh, spot_c_kwh, total_c_kwh)
            VALUES ('FI', $1, 24, 70.00, 7.00, 11.70)
            """,
            date(2025, 1, 17),
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
