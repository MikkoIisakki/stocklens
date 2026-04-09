---
name: caching-strategy
description: When and what to cache, Redis cache patterns, TTL strategy, cache invalidation, and what must never be cached in the stocklens system. For architect and engineer use.
---

# Caching Strategy

## Principle: Cache Pre-Computed Results, Not Raw Data

The system already pre-computes factors and scores. Caching is a second layer of acceleration on top of that — not a substitute for pre-computation. Raw price data and factor computation must never be served from cache — only final, materialized results.

**Add caching only when**: a query is demonstrably slow under real load OR when the same expensive query is called repeatedly within a short window.

**Do not add caching speculatively.** Profile first (`pg_stat_statements`), then cache.

---

## What to Cache and TTL

| Data | Cache key | TTL | Reason |
|---|---|---|---|
| Daily rankings (top N) | `rankings:daily:{market}:{horizon}:{limit}` | Until next score update (~24h) | Most-read endpoint; rankings don't change until next scoring run |
| Latest score per asset | `score:{symbol}:{horizon}` | Until next score update (~24h) | High read frequency on screener pages |
| Asset metadata | `asset:{symbol}` | 24h | Reference data changes rarely |
| Active ticker list | `assets:active:{market}` | 1h | Changes only when tickers are added/deactivated |
| Screener results | `screener:{market}:{horizon}:{filters_hash}` | 1h | Common filter combinations repeated often |
| Macro indicators | `macro:{series_id}` | 12h | Updates weekly or monthly |
| News sentiment | `sentiment:{symbol}` | 6h | Staleness acceptable; updates daily |

**Never cache:**
- Raw API responses (those go in `raw_source_snapshot`)
- Individual price rows
- Alert events (must always reflect current DB state)
- Anything security-sensitive

---

## Redis as Cache

Redis is the cache store. Add it to Docker Compose only when caching is actually needed (Phase 2+).

```yaml
# docker-compose.yml addition
redis:
  image: redis:7-alpine
  command: redis-server --save "" --maxmemory 256mb --maxmemory-policy allkeys-lru
  volumes:
    - redis_data:/data
  networks:
    - back-tier
```

`maxmemory-policy allkeys-lru` — Redis evicts least-recently-used keys when memory is full. Appropriate for a cache (data is reproducible from DB).

---

## Cache Pattern: Cache-Aside (Lazy Loading)

The recommended pattern. Application checks cache first; on miss, reads from DB and populates cache.

```python
# common/cache.py
import redis.asyncio as redis
import json
from typing import Any, Callable, Awaitable

class Cache:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def get_or_set(
        self,
        key: str,
        ttl_seconds: int,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Cache-aside: return cached value or load, cache, and return."""
        cached = await self._client.get(key)
        if cached is not None:
            return json.loads(cached)

        value = await loader()
        await self._client.setex(key, ttl_seconds, json.dumps(value))
        return value
```

```python
# Usage in storage/scores.py
async def get_daily_rankings(
    conn: asyncpg.Connection,
    cache: Cache,
    market: str,
    horizon: str,
    limit: int,
) -> list[dict]:
    key = f"rankings:daily:{market}:{horizon}:{limit}"
    ttl = 3600  # 1 hour

    return await cache.get_or_set(
        key, ttl,
        loader=lambda: _fetch_rankings_from_db(conn, market, horizon, limit)
    )
```

---

## Cache Invalidation

Cache invalidation is the hardest part. Use **event-driven invalidation** tied to the scoring pipeline:

```python
# jobs/worker.py — after scoring run completes
async def on_scoring_complete(cache: Cache, symbols: list[str]) -> None:
    """Invalidate all cached scores and rankings after a scoring run."""
    keys_to_delete = []

    # Per-symbol score caches
    for symbol in symbols:
        keys_to_delete.append(f"score:{symbol}:long_term")
        keys_to_delete.append(f"score:{symbol}:short_term")

    # Rankings (invalidate all market/horizon combinations)
    for market in ["US", "FI"]:
        for horizon in ["long_term", "short_term"]:
            pattern = f"rankings:daily:{market}:{horizon}:*"
            async for key in cache.scan(pattern):
                keys_to_delete.append(key)

    if keys_to_delete:
        await cache.delete(*keys_to_delete)
```

**Never use TTL-only invalidation for score data** — stale scores mislead investment decisions. Always invalidate explicitly after a scoring run.

---

## Cache Key Naming Convention

```
{resource}:{identifier}:{variant}
```

Examples:
```
asset:AAPL
score:AAPL:long_term
score:NOKIA.HE:short_term
rankings:daily:US:long_term:20
screener:US:long_term:min_score=25:sector=Technology
assets:active:FI
macro:T10Y2Y
```

For screener queries with arbitrary filters, hash the sorted filter parameters:
```python
import hashlib, json

def screener_cache_key(market: str, horizon: str, filters: dict) -> str:
    filter_hash = hashlib.md5(
        json.dumps(filters, sort_keys=True).encode()
    ).hexdigest()[:8]
    return f"screener:{market}:{horizon}:{filter_hash}"
```

---

## What Not to Cache — Decision Table

| Reason | Example |
|---|---|
| Data changes on every request | Alert event acknowledgement |
| Data must be real-time accurate | Active ingest run status |
| Data is user-specific (Phase 4) | Watchlist contents per user — cache per user ID |
| Data volume is tiny | Asset metadata for a single symbol — DB lookup is < 1ms |
| Caching would hide a bad query | If caching because the query is slow, fix the query first |

---

## Testing Cache Behaviour

```python
# tests/unit/test_cache.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_cache_aside_returns_cached_value_on_hit():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b'{"score": 75.0}'
    cache = Cache(mock_redis)
    loader = AsyncMock()

    result = await cache.get_or_set("score:AAPL:long_term", 3600, loader)

    assert result == {"score": 75.0}
    loader.assert_not_called()   # DB not hit on cache hit

@pytest.mark.asyncio
async def test_cache_aside_populates_on_miss():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None   # cache miss
    cache = Cache(mock_redis)
    loader = AsyncMock(return_value={"score": 42.0})

    result = await cache.get_or_set("score:AAPL:long_term", 3600, loader)

    assert result == {"score": 42.0}
    loader.assert_called_once()
    mock_redis.setex.assert_called_once()
```

---

## ADR Reference

Before adding Redis/caching, write ADR-004 covering:
- Why caching is needed now (profiling evidence)
- TTL choices per data type
- Invalidation strategy
- What happens if Redis is unavailable (fall through to DB — cache must be optional)
