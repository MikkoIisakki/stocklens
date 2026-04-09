---
name: clean-architecture
description: Clean Architecture principles applied to the pulse system. Based on Robert C. Martin's Clean Architecture. Defines dependency rules, layer boundaries, and how domain logic is protected from infrastructure concerns. For architect use.
---

# Clean Architecture

Based on Robert C. Martin's *Clean Architecture* and Domain-Driven Design principles. The goal is a system where business rules are independent of frameworks, databases, and external APIs — they can be tested without any infrastructure running.

---

## The Dependency Rule

**Source code dependencies must point inward. Inner layers know nothing about outer layers.**

```
┌─────────────────────────────────────────────┐
│  Frameworks & Drivers (outermost)           │
│  FastAPI, asyncpg, yfinance, APScheduler    │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Interface Adapters                   │  │
│  │  routers/, storage/, ingestion/       │  │
│  │                                       │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │  Application / Use Cases        │  │  │
│  │  │  signals/, scoring/, alerts/    │  │  │
│  │  │  ranking/, jobs/                │  │  │
│  │  │                                 │  │  │
│  │  │  ┌───────────────────────────┐  │  │  │
│  │  │  │  Domain / Entities        │  │  │  │
│  │  │  │  common/types.py          │  │  │  │
│  │  │  │  Pydantic domain models   │  │  │  │
│  │  │  │  Domain exceptions        │  │  │  │
│  │  │  └───────────────────────────┘  │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘

Arrows point inward only. Domain never imports from storage. Scoring never imports from routers.
```

---

## Layers in the Stocklens

### Layer 1 — Domain Entities (`common/types.py`)
Pure Python data classes and domain exceptions. No imports from any other project module. No framework dependencies.

```python
# common/types.py — domain objects
@dataclass(frozen=True)
class Signal:
    name: str
    value: float | None
    signal_type: str   # 'bullish' | 'bearish' | 'neutral' | 'unavailable'
    weight: float

@dataclass(frozen=True)
class FactorSnapshot:
    symbol: str
    as_of_date: date
    rsi_14: float | None
    macd_signal: str | None
    eps_growth_acceleration: float | None
    # ... all factor fields

class DomainError(Exception): ...
class IngestionError(DomainError): ...
class NoDataError(DomainError): ...
class ScoringError(DomainError): ...
```

**Allowed imports**: Python stdlib only (`datetime`, `dataclasses`, `enum`)

---

### Layer 2 — Use Cases (`signals/`, `scoring/`, `alerts/`, `ranking/`, `jobs/`)
Business rules. Orchestrates domain entities. Calls storage interfaces via dependency injection — never imports `asyncpg` directly.

```python
# signals/technical.py — use case
from app.common.types import Signal, FactorSnapshot
# ✓ imports domain types
# ✗ never imports asyncpg, FastAPI, yfinance

def compute_rsi_signal(prices: pd.Series) -> Signal:
    """Pure function. No I/O. Fully unit-testable."""
    ...
```

**Allowed imports**: `common/types`, `common/config`, Python stdlib, `pandas`, `pandas-ta`, `numpy`

**Not allowed**: `asyncpg`, `fastapi`, `yfinance`, any `storage/` module

---

### Layer 3 — Interface Adapters (`storage/`, `ingestion/`, `normalization/`, `api/routers/`)
Converts data between domain format and external format (DB rows, HTTP responses, API payloads).

```python
# storage/assets.py — adapter
import asyncpg
from app.common.types import Asset

async def get_asset(conn: asyncpg.Connection, symbol: str) -> Asset | None:
    row = await conn.fetchrow("SELECT * FROM asset WHERE symbol = $1", symbol)
    if row is None:
        return None
    return Asset(**dict(row))   # converts DB row → domain type
```

```python
# api/routers/assets.py — adapter
from fastapi import APIRouter
from app.storage import assets as asset_repo   # ✓ imports storage adapter
# ✗ never imports signals/, scoring/ — no business logic in routers

@router.get("/assets/{symbol}")
async def get_asset(symbol: str, conn=Depends(get_conn)):
    asset = await asset_repo.get_asset(conn, symbol)
    if asset is None:
        raise HTTPException(404, ...)
    return AssetResponse.from_domain(asset)
```

**Allowed imports**: `common/`, `asyncpg`, `fastapi`, framework libraries

---

### Layer 4 — Frameworks & Drivers (`main.py`, `jobs/scheduler.py`, external libs)
Wiring. Plugs everything together. Contains no business logic.

```python
# main.py — framework layer
from fastapi import FastAPI
from app.api.routers import assets, rankings, alerts

app = FastAPI()
app.include_router(assets.router, prefix="/v1")
app.include_router(rankings.router, prefix="/v1")
```

---

## Dependency Inversion in Practice

Use cases must not depend on storage implementations directly. Use **protocol interfaces** so the use case is testable without a DB:

```python
# common/ports.py — abstract interfaces (ports)
from typing import Protocol

class AssetRepository(Protocol):
    async def get_asset(self, symbol: str) -> Asset | None: ...
    async def list_active(self, market: str | None = None) -> list[Asset]: ...

class PriceRepository(Protocol):
    async def get_prices(self, symbol: str, days: int) -> list[DailyPrice]: ...
```

```python
# signals/fundamental.py — use case depends on protocol, not implementation
async def compute_fundamental_signals(
    symbol: str,
    prices: PriceRepository,       # ← protocol, not asyncpg
    fundamentals: FundamentalRepository,
) -> dict[str, Signal]: ...
```

```python
# In tests — inject a fake, no DB needed
class FakePriceRepository:
    def __init__(self, data): self._data = data
    async def get_prices(self, symbol, days): return self._data

# In production — inject the real asyncpg-backed implementation
```

---

## Screaming Architecture

**The top-level structure should scream what the system does, not what framework it uses.**

```
# Bad — screams "it's a web app"
app/
  controllers/
  models/
  views/

# Good — screams "it's a stock screening system"
app/
  signals/          ← computes investment signals
  scoring/          ← scores and ranks assets
  alerts/           ← evaluates alert rules
  ingestion/        ← fetches market data
  ranking/          ← materialises daily rankings
```

Framework names (`fastapi/`, `sqlalchemy/`) belong in the outermost layer, not the top level.

---

## Boundaries and the Anti-Corruption Layer

Where the system touches external APIs (yfinance, Alpha Vantage, FRED, Finnhub), use a thin **anti-corruption layer** in `normalization/` that translates external data formats into domain types. The rest of the system never sees yfinance DataFrames or Alpha Vantage JSON dicts.

```python
# normalization/yfinance.py — anti-corruption layer
def normalize_ohlcv(raw_df: pd.DataFrame, symbol: str) -> list[DailyPrice]:
    """Translate yfinance DataFrame → domain DailyPrice objects."""
    return [
        DailyPrice(
            symbol=symbol,
            date=idx.date(),
            open=row["Open"],
            close=row["Close"],
            ...
        )
        for idx, row in raw_df.iterrows()
    ]
```

If yfinance changes its column names tomorrow, only `normalization/yfinance.py` changes.

---

## Architecture Fitness Functions

These tests verify architectural rules are not violated — run them in CI:

```python
# tests/architecture/test_dependency_rules.py
import ast, pathlib

def test_domain_has_no_external_imports():
    """common/types.py must not import from asyncpg, fastapi, or yfinance."""
    source = pathlib.Path("backend/app/common/types.py").read_text()
    tree = ast.parse(source)
    forbidden = {"asyncpg", "fastapi", "yfinance", "storage", "api"}
    imports = {node.names[0].name.split(".")[0]
               for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom))}
    violations = imports & forbidden
    assert not violations, f"Domain layer imports infrastructure: {violations}"

def test_signals_do_not_import_storage():
    """signals/ must not import from storage/."""
    for path in pathlib.Path("backend/app/signals").glob("*.py"):
        source = path.read_text()
        assert "from app.storage" not in source, \
            f"{path.name} imports storage — violates dependency rule"

def test_routers_do_not_import_signals():
    """Routers must not import business logic directly."""
    for path in pathlib.Path("backend/app/api/routers").glob("*.py"):
        source = path.read_text()
        assert "from app.signals" not in source, \
            f"{path.name} imports signals — business logic in router"
        assert "from app.scoring" not in source, \
            f"{path.name} imports scoring — business logic in router"
```
