---
name: clean-code
description: Clean code principles and practices for the stocklens codebase. Based on Robert C. Martin's Clean Code and related practices. Mandatory for the engineer agent.
---

# Clean Code

Based on Robert C. Martin's *Clean Code*, Martin Fowler's *Refactoring*, and related practitioner standards. These are not suggestions — they are the bar every implementation must meet.

---

## Naming

**Names must reveal intent. If a name requires a comment, rename it.**

```python
# Bad
d = 86400
def calc(p, d):
    return p * (1 + d) ** (1/365)

# Good
SECONDS_PER_DAY = 86400
def annualized_return(price_series: pd.Series, annual_rate: float) -> float:
    daily_rate = (1 + annual_rate) ** (1 / 365) - 1
    return price_series * (1 + daily_rate)
```

Rules:
- **Classes**: nouns — `EarningsSignal`, `AssetRepository`, `RuleBasedScorer`
- **Functions**: verb phrases — `compute_rsi`, `fetch_daily_prices`, `evaluate_alert_rules`
- **Booleans**: questions — `is_market_open`, `has_sufficient_data`, `was_ingested_today`
- **No abbreviations** unless universally known (`rsi`, `macd`, `eps` are domain-standard)
- **No single-letter variables** except loop counters and well-known math (`i`, `n`, `x`, `y`)
- **No type suffixes** — `asset_list` → `assets`, `price_dict` → `prices_by_symbol`

---

## Functions

**A function does one thing. If you can extract a meaningful sub-function, it does more than one thing.**

```python
# Bad — does fetching, normalising, saving, and triggering in one function
async def process_ticker(symbol: str, conn) -> None:
    raw = yf.Ticker(symbol).history(period="1y")
    df = raw.rename(columns={"Open": "open", "Close": "close"})
    await conn.execute("INSERT INTO daily_price ...", ...)
    await publish_task("process_signals", symbol)

# Good — each step is named and independently testable
async def ingest_daily_prices(symbol: str, conn) -> None:
    raw = await fetch_yfinance_history(symbol, period="1y")
    await save_raw_snapshot(conn, symbol, "yfinance", "history", raw)
    prices = normalize_ohlcv(raw, symbol)
    await upsert_daily_prices(conn, prices)
    await publish_process_task(symbol)
```

Rules:
- **Small** — if it doesn't fit on one screen, it probably does too much
- **One level of abstraction per function** — don't mix high-level orchestration with low-level detail
- **No side effects** — a function named `compute_rsi` must not write to the DB
- **Maximum 3 parameters** — if you need more, introduce a data class
- **No boolean flag parameters** — `fetch(symbol, include_fundamentals=True)` → split into two functions
- **Command/Query separation** — a function either returns a value OR causes a side effect, not both

---

## Classes

```python
# Single Responsibility — one reason to change
class RuleBasedScorer:
    """Computes composite score from a factor snapshot."""
    # Only scoring logic here — no DB, no API calls, no config loading

class AssetRepository:
    """All DB operations for the asset table."""
    # Only data access — no business logic
```

Rules:
- **Single Responsibility Principle** — one class, one reason to change
- **Small** — if a class needs a table of contents, split it
- **Cohesion** — all methods use most of the instance variables; if not, extract a class
- **No God classes** — a class named `Manager`, `Handler`, or `Processor` is a smell

---

## Comments

**Good code is self-documenting. Comments explain why, not what.**

```python
# Bad — restates the code
# Add 1 to i
i += 1

# Bad — describes what the code does (the code already does that)
# Compute the RSI signal
rsi = compute_rsi(prices)

# Good — explains why (not obvious from code)
# Skip the last day — yfinance returns it as partial if market is still open
prices = prices.iloc[:-1]

# Good — names a design pattern being applied
# Strategy Pattern: scorer is injected so it can be swapped for ML model later
score = self._scorer.score(factors)
```

Rules:
- **No commented-out code** — delete it; git history preserves it
- **No redundant comments** — if the code is clear, no comment needed
- **TODO comments** are technical debt — create a story in the backlog instead
- **Legal/licence headers** belong in files; other file-level context belongs in the module docstring

---

## Error Handling

```python
# Bad — swallows errors silently
try:
    prices = fetch_yfinance_history(symbol)
except Exception:
    pass

# Bad — uses error codes instead of exceptions
def get_asset(symbol: str) -> Asset | None:
    ...
    return None  # caller might not check

# Good — specific exceptions, logged, re-raised or handled explicitly
async def fetch_yfinance_history(symbol: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(symbol).history(period="1y")
    except Exception as e:
        logger.error("yfinance fetch failed", symbol=symbol, error=str(e))
        raise IngestionError(f"Failed to fetch {symbol} from yfinance") from e
    if df.empty:
        raise NoDataError(f"yfinance returned empty data for {symbol}")
    return df
```

Rules:
- **Never swallow exceptions** — at minimum log and re-raise
- **Use specific exception types** — define domain exceptions (`IngestionError`, `NoDataError`, `ScoringError`)
- **Fail fast** — validate inputs at boundaries; don't propagate bad data deep into the system
- **Don't return `None` to indicate failure** — raise an exception or use `Result` typing

---

## Data / State

```python
# Bad — mutable default arguments
def compute_signals(prices, indicators=["RSI", "MACD"]):  # shared mutable state

# Bad — data clumps (always passed together → make a class)
def score(rsi, macd, volume, eps_growth, revenue_growth, margin_delta):
    ...

# Good — cohesive data class
@dataclass(frozen=True)  # immutable where possible
class FactorSnapshot:
    symbol: str
    as_of_date: date
    rsi_14: float | None
    macd_signal: str | None
    eps_growth_acceleration: float | None
    ...
```

Rules:
- **Immutable by default** — use `frozen=True` dataclasses or Pydantic models
- **No mutable default arguments** in function signatures
- **Don't pass primitives when you mean domain objects** — `symbol: str` is fine for a repository call; `price: float` in a scoring function should be `FactorSnapshot`
- **No global mutable state** — config is read-only after startup

---

## DRY and YAGNI

- **DRY** (Don't Repeat Yourself) — if you copy-paste logic twice, extract it. Third copy is a rule.
- **YAGNI** (You Aren't Gonna Need It) — don't build for hypothetical future requirements. Implement what the AC requires.
- **Rule of Three**: tolerate duplication once, refactor on the third occurrence

---

## Boy Scout Rule

**Leave the code cleaner than you found it.**

If you touch a file and see a naming issue, an unnecessary comment, or a function that does two things — fix it in the same PR. Small, continuous improvement prevents rot.
