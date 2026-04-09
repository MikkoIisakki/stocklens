---
name: test-driven-development
description: TDD process, test pyramid, pytest conventions, fixture patterns, and how to write Given/When/Then tests for the pulse codebase. For engineer use.
---

# Test-Driven Development

## The TDD Cycle

**Red → Green → Refactor. Always in this order.**

```
1. Read the acceptance criterion (Given/When/Then from product-manager)
2. Write a test that captures the criterion — run it, confirm it FAILS (Red)
3. Write the minimum code to make it pass — run it, confirm it PASSES (Green)
4. Clean up the code without breaking the test (Refactor)
5. Repeat for the next criterion
```

If you write code before a failing test exists, you are not doing TDD. Stop, write the test first.

## Test Pyramid

```
        /\
       /  \   E2E (rare — manual or smoke tests only)
      /────\
     / Integ \  Integration tests — real DB, real FastAPI client
    /──────────\
   /   Unit     \  Unit tests — pure functions, no I/O, fast
  /______________\
```

- **Unit tests**: majority of tests. Pure functions. No DB, no network. Run in < 1s total.
- **Integration tests**: real PostgreSQL via Docker. Cover storage layer and API endpoints. Run in CI.
- **E2E**: manual verification only (for now). `docker compose up` + manual API calls.

## Pytest Conventions

### File structure
```
tests/
  unit/
    signals/
      test_technical.py
      test_fundamental.py
      test_sentiment.py
    scoring/
      test_rule_based.py
    normalization/
      test_normalizers.py
    common/
      test_market_hours.py
  integration/
    test_storage_assets.py
    test_storage_prices.py
    test_storage_factors.py
    test_api_assets.py
    test_api_rankings.py
  conftest.py
```

### Test naming
`test_<what>_<condition>_<expected>`:
```python
def test_rsi_below_30_returns_bullish_signal(): ...
def test_score_with_no_signals_returns_hold(): ...
def test_get_asset_unknown_symbol_returns_404(): ...
```

### Given/When/Then in test structure

Map acceptance criteria directly to test structure using comments:

```python
def test_daily_price_history_returns_correct_range():
    # Given: AAPL has 60 days of price data in the DB
    # When: GET /v1/assets/AAPL/prices?days=30
    # Then: returns exactly 30 rows, descending date order
    #   And: each row has date, open, high, low, close, volume

    seed_prices(symbol="AAPL", days=60)

    response = client.get("/v1/assets/AAPL/prices?days=30")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 30
    assert data[0]["date"] > data[-1]["date"]   # descending
    assert all({"date","open","high","low","close","volume"} <= set(row) for row in data)
```

## Fixtures

Define all shared fixtures in `tests/conftest.py`:

```python
import pytest
import asyncpg

@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DATABASE_URL)
    yield pool
    await pool.close()

@pytest.fixture(autouse=True)
async def clean_db(db_pool):
    """Truncate all tables before each test to ensure isolation."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE asset, daily_price, factor_snapshot, score_snapshot,
                     raw_source_snapshot, ingest_run, alert_rule, alert_event
            RESTART IDENTITY CASCADE
        """)
    yield

@pytest.fixture
def client(db_pool):
    """FastAPI TestClient with real DB pool injected."""
    from httpx import AsyncClient
    from app.main import app
    return AsyncClient(app=app, base_url="http://test")

# Data factory fixtures
@pytest.fixture
def make_asset(db_pool):
    async def _make(symbol="AAPL", market="US", **kwargs):
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO asset (symbol, name, exchange, market, currency) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                symbol, kwargs.get("name", symbol), kwargs.get("exchange", "NASDAQ"),
                market, kwargs.get("currency", "USD")
            )
        return symbol
    return _make
```

## Unit Test Patterns

Pure functions need no fixtures — just call and assert:

```python
# tests/unit/signals/test_technical.py
import pandas as pd
from app.signals.technical import compute_rsi_signal

def test_rsi_below_30_is_bullish():
    # Given: 14 days of prices trending down (RSI will be < 30)
    prices = pd.Series([100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74])
    # When
    signal = compute_rsi_signal(prices)
    # Then
    assert signal.signal_type == "bullish"
    assert signal.value < 30

def test_rsi_with_insufficient_data_returns_unavailable():
    prices = pd.Series([100, 98])  # less than 14 days
    signal = compute_rsi_signal(prices)
    assert signal.signal_type == "unavailable"
    assert signal.weight == 0.0
```

## Integration Test Patterns

```python
# tests/integration/test_api_assets.py
import pytest

@pytest.mark.asyncio
async def test_get_asset_returns_detail(client, make_asset):
    # Given
    await make_asset("AAPL", market="US", name="Apple Inc.")
    # When
    response = await client.get("/v1/assets/AAPL")
    # Then
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["symbol"] == "AAPL"
    assert data["market"] == "US"

@pytest.mark.asyncio
async def test_get_unknown_asset_returns_404(client):
    # Given: no assets in DB (clean_db fixture)
    # When
    response = await client.get("/v1/assets/INVALID")
    # Then
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ASSET_NOT_FOUND"
```

## What NOT to Mock

- **PostgreSQL** — always use a real test DB. Mock DB = false confidence.
- **Pure functions** — don't mock your own code; test it directly.

**Mock only**:
- External HTTP APIs (yfinance, Alpha Vantage, FRED, Finnhub) in unit tests — use `pytest-mock` or `responses` library
- Clock/time in market hours tests — use `freezegun`

## Running Tests

```bash
# All tests
pytest -q

# Unit tests only (fast)
pytest tests/unit/ -q

# Integration tests only
pytest tests/integration/ -q

# Specific file
pytest tests/unit/signals/test_technical.py -v

# With coverage
pytest --cov=app --cov-report=term-missing
```
