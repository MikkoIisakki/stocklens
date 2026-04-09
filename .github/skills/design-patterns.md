---
name: design-patterns
description: Software design patterns applicable to the stocklens codebase. When to use each, and how they map to specific modules. For architect and engineer use.
---

# Design Patterns

## Patterns in Use

### Repository Pattern
**Where**: `storage/` module  
**What**: Encapsulates all data access behind a clean interface. Domain modules call repository functions — they never know if data comes from PostgreSQL, a cache, or a test fixture.

```python
# storage/assets.py
async def get_asset(conn, symbol: str) -> Asset | None: ...
async def list_active_assets(conn, market: str | None = None) -> list[Asset]: ...
async def upsert_asset(conn, asset: Asset) -> None: ...
```

Domain code calls `storage.assets.get_asset(conn, "AAPL")` — never raw SQL.

---

### Strategy Pattern
**Where**: `scoring/`, `signals/`  
**What**: Defines a family of interchangeable algorithms behind a common interface. Scoring strategies (rule-based, ML-based) can be swapped without changing the caller.

```python
class ScoringStrategy(Protocol):
    def score(self, factors: FactorSnapshot) -> ScoreResult: ...

class RuleBasedScorer:
    def score(self, factors: FactorSnapshot) -> ScoreResult: ...

class MLScorer:            # Phase 4
    def score(self, factors: FactorSnapshot) -> ScoreResult: ...
```

Scorer is injected into the scoring pipeline — switching from rule-based to ML requires no changes to the pipeline code.

---

### Template Method Pattern
**Where**: `ingestion/` consumers  
**What**: Defines the skeleton of an algorithm in a base class, letting subclasses fill in the steps. All ingesters share the same flow (fetch → save raw → normalize → upsert) with source-specific implementations.

```python
class BaseIngester:
    async def run(self, symbol: str, conn) -> None:
        raw = await self.fetch(symbol)           # abstract
        await save_raw_snapshot(conn, raw)        # shared
        normalized = self.normalize(raw)          # abstract
        await self.upsert(conn, normalized)       # shared

class YFinanceIngester(BaseIngester):
    async def fetch(self, symbol: str): ...
    def normalize(self, raw): ...
```

---

### Factory Pattern
**Where**: `ingestion/` dispatcher, `scoring/` selector  
**What**: Creates the correct object based on a parameter, without the caller knowing the concrete type.

```python
def get_ingester(source: str) -> BaseIngester:
    match source:
        case "yfinance":      return YFinanceIngester()
        case "alphavantage":  return AlphaVantageIngester()
        case "fred":          return FREDIngester()
        case "finnhub":       return FinnhubIngester()
        case _:               raise ValueError(f"Unknown source: {source}")
```

---

### Observer / Event Pattern
**Where**: Ingestion → scoring pipeline trigger  
**What**: After ingestion completes, an event is published that triggers the scoring worker. Decouples the two without a direct call.

Currently implemented as: ingester writes `ingest_run` record with `status=success` → scheduler polls and triggers scoring job. If Redis is added, publish to a stream instead.

---

### Decorator Pattern
**Where**: `common/`, scheduler  
**What**: Wraps functions to add cross-cutting behavior (retry, logging, timing) without modifying the function.

```python
# Retry decorator for external API calls
@retry(max_attempts=3, backoff_factor=2.0)
async def fetch_prices(symbol: str) -> pd.DataFrame: ...

# Market hours guard
@market_hours_only
async def ingest_intraday(symbol: str) -> None: ...
```

---

### Null Object Pattern
**Where**: Signal computation  
**What**: Return a neutral signal object instead of `None` when data is unavailable. Prevents None-checks scattered through scoring code.

```python
@dataclass
class Signal:
    name: str
    value: float | None
    signal_type: str      # 'bullish', 'bearish', 'neutral', 'unavailable'
    weight: float

# When RSI data unavailable:
Signal(name="RSI", value=None, signal_type="unavailable", weight=0.0)
# Scorer skips weight=0.0 signals cleanly — no if-None checks
```

---

### SOLID Principles Applied

| Principle | How it applies |
|---|---|
| **Single Responsibility** | Each module owns one concern: `storage/` owns DB, `signals/` owns computation, `api/` owns HTTP |
| **Open/Closed** | Add new signals by adding a new function to `signals/` — never modify existing signal functions |
| **Liskov Substitution** | All ingesters are substitutable via `BaseIngester`; all scorers via `ScoringStrategy` |
| **Interface Segregation** | Storage functions are split by domain (`assets.py`, `prices.py`, `factors.py`) — callers import only what they need |
| **Dependency Inversion** | Domain modules depend on `storage/` abstractions, not on `asyncpg` directly |

---

## Anti-Patterns to Avoid

| Anti-pattern | Example | Why |
|---|---|---|
| **God module** | `utils.py` with 500 lines | No clear responsibility; becomes a dumping ground |
| **Primitive obsession** | Passing `str` symbol everywhere instead of `Asset` | Loses type safety and domain meaning |
| **Anemic domain model** | Pydantic models with no methods, all logic in service functions | Fine for data models, but signal logic belongs near the signal type |
| **Shotgun surgery** | Adding a new market requires changes in 8 different files | Signals a missing abstraction — should be one place |
| **Premature abstraction** | Base class for two implementations that are identical | Wait until the third implementation before abstracting |
