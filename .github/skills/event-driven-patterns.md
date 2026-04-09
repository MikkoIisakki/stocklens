---
name: event-driven-patterns
description: Redis Streams, consumer groups, at-least-once delivery, backpressure, and event-driven pipeline patterns for the stocklens system. For architect and engineer use.
---

# Event-Driven Patterns

## Current State vs Future State

**Phase 1–2 (current)**: The scheduler calls ingest functions directly. APScheduler triggers jobs in-process. Simple, no message queue needed.

**Phase 2+ (when to add)**: Add Redis Streams when:
- Ingest and scoring need to be decoupled (ingest completes → scoring triggered automatically)
- Multiple worker processes need to share a work queue without duplicate processing
- You need durable task delivery (task survives a worker crash)

This skill documents the patterns to use when that time comes. Do not implement prematurely.

---

## Redis Streams Concepts

Redis Streams are an append-only log with consumer group support. Key differences from pub/sub:

| Feature | Pub/Sub | Streams |
|---|---|---|
| Durability | Messages lost if no subscriber | Messages persisted until acknowledged |
| Consumer groups | No | Yes — multiple workers share a stream |
| At-least-once delivery | No | Yes — unacknowledged messages are re-delivered |
| Backpressure | No | Yes — `MAXLEN` limits stream size |
| Replay | No | Yes — read from any offset |

---

## Stream Design for Stocklens

```
tasks:ingest  ← scheduler publishes ingest tasks
      │
      └── consumer group: ingester-workers
            ├── worker-1: fetches yfinance prices
            ├── worker-2: fetches yfinance prices
            └── worker-3: fetches Alpha Vantage fundamentals

tasks:process ← ingester publishes after each successful ingest
      │
      └── consumer group: processor-workers
            ├── worker-1: computes signals + scores for AAPL
            └── worker-2: computes signals + scores for NOKIA.HE
```

### Stream naming convention
```
tasks:{job_type}       — task queue (ingest tasks, process tasks)
events:{event_type}    — events (ingest completed, score updated)
```

---

## Publishing Tasks

```python
# common/streams.py
import redis.asyncio as redis
import json
from datetime import datetime, timezone

async def publish_task(
    client: redis.Redis,
    stream: str,
    payload: dict,
    maxlen: int = 10_000,
) -> str:
    """Publish a task to a Redis Stream. Returns the message ID."""
    message = {
        "payload": json.dumps(payload),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    msg_id = await client.xadd(stream, message, maxlen=maxlen, approximate=True)
    return msg_id

# Usage in scheduler
await publish_task(redis_client, "tasks:ingest", {
    "type": "daily_prices",
    "symbol": "AAPL",
    "source": "yfinance",
    "interval": "1d",
})
```

`maxlen=10_000, approximate=True` — Redis trims the stream to ~10k messages efficiently. Prevents unbounded memory growth.

---

## Consuming with Consumer Groups

```python
# common/streams.py
async def create_consumer_group(
    client: redis.Redis,
    stream: str,
    group: str,
) -> None:
    """Create consumer group if it doesn't exist. Safe to call on startup."""
    try:
        await client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise  # group already exists — ignore, re-raise anything else

async def consume_stream(
    client: redis.Redis,
    stream: str,
    group: str,
    consumer: str,
    batch_size: int = 10,
    block_ms: int = 5000,
) -> list[tuple[str, dict]]:
    """
    Read pending messages first, then new ones.
    Returns list of (message_id, payload) tuples.
    """
    # First: re-deliver pending messages from previous crashes
    pending = await client.xreadgroup(
        group, consumer, {stream: "0"},
        count=batch_size
    )
    if pending and pending[0][1]:
        return [(msg_id, json.loads(data[b"payload"]))
                for msg_id, data in pending[0][1]]

    # Then: read new messages (blocks up to block_ms if empty)
    messages = await client.xreadgroup(
        group, consumer, {stream: ">"},
        count=batch_size,
        block=block_ms,
    )
    if not messages:
        return []
    return [(msg_id, json.loads(data[b"payload"]))
            for msg_id, data in messages[0][1]]

async def acknowledge(
    client: redis.Redis,
    stream: str,
    group: str,
    message_id: str,
) -> None:
    """Acknowledge successful processing. Message removed from PEL."""
    await client.xack(stream, group, message_id)
```

---

## Worker Loop — At-Least-Once Delivery

```python
# jobs/worker.py
async def run_worker(redis_client, db_pool, consumer_name: str) -> None:
    """Main worker loop. Processes tasks from Redis Stream with at-least-once delivery."""
    await create_consumer_group(redis_client, "tasks:ingest", "ingester-workers")

    logger.info("Worker started", consumer=consumer_name)

    while True:
        messages = await consume_stream(
            redis_client, "tasks:ingest", "ingester-workers", consumer_name
        )

        for msg_id, payload in messages:
            try:
                await process_task(db_pool, redis_client, payload)
                await acknowledge(redis_client, "tasks:ingest", "ingester-workers", msg_id)
                logger.info("Task completed", msg_id=msg_id, task_type=payload["type"])

            except IngestionError as e:
                # Known, recoverable error — log and acknowledge to avoid infinite retry
                logger.error("Ingestion failed", msg_id=msg_id, error=str(e), payload=payload)
                await acknowledge(redis_client, "tasks:ingest", "ingester-workers", msg_id)

            except Exception as e:
                # Unknown error — do NOT acknowledge; message re-delivered after timeout
                logger.critical("Unexpected error", msg_id=msg_id, error=str(e))
                # Worker continues; message stays in PEL until claimed by another worker
```

**At-least-once delivery**: a message is only removed from the Pending Entry List (PEL) after `XACK`. If the worker crashes before acknowledging, the message is re-delivered to another worker.

**Idempotency requirement**: because messages may be processed more than once, all handlers must be idempotent. `INSERT ... ON CONFLICT DO UPDATE` in storage functions ensures this.

---

## Dead Letter Handling

Messages that fail repeatedly must be moved to a dead letter stream, not left in the PEL indefinitely:

```python
MAX_DELIVERY_ATTEMPTS = 3

async def check_and_move_dead_letters(
    client: redis.Redis,
    stream: str,
    group: str,
    dead_letter_stream: str = "tasks:dead-letter",
) -> None:
    """Move messages that have exceeded max delivery attempts."""
    # Get pending messages older than 5 minutes
    pending = await client.xpending_range(
        stream, group,
        min="-", max="+",
        count=100,
        idle=300_000,  # 5 minutes in ms
    )

    for entry in pending:
        if entry["times_delivered"] >= MAX_DELIVERY_ATTEMPTS:
            # Claim and move to dead letter stream
            claimed = await client.xautoclaim(
                stream, group, "dead-letter-handler",
                min_idle_time=300_000,
                start=entry["message_id"],
                count=1,
            )
            if claimed[1]:
                msg_id, data = claimed[1][0]
                await client.xadd(dead_letter_stream, {
                    **data,
                    "original_stream": stream,
                    "original_id": msg_id,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                })
                await client.xack(stream, group, msg_id)
                logger.error("Message moved to dead letter", original_id=msg_id)
```

Monitor `tasks:dead-letter` in Grafana to detect systematic failures.

---

## Backpressure

If the ingest stream grows faster than workers can process it, apply backpressure in the scheduler:

```python
# jobs/scheduler.py
MAX_PENDING_TASKS = 500

async def publish_ingest_tasks_if_capacity(redis_client, symbols) -> None:
    """Only publish if stream is not overloaded."""
    info = await redis_client.xinfo_stream("tasks:ingest")
    pending_count = info["length"]

    if pending_count > MAX_PENDING_TASKS:
        logger.warning(
            "Ingest stream backlog too large — skipping this cycle",
            pending=pending_count,
            max=MAX_PENDING_TASKS,
        )
        return

    for symbol in symbols:
        await publish_task(redis_client, "tasks:ingest", {...})
```

---

## Pipeline Event Flow (Phase 2+)

```
Scheduler
  │ publishes tasks:ingest
  ▼
Ingester worker (consumer group)
  │ fetches data → saves raw snapshot → normalizes → upserts to DB
  │ publishes tasks:process with symbol + as_of_date
  ▼
Processor worker (consumer group)
  │ reads prices + fundamentals from DB
  │ computes signals → factor_snapshot
  │ computes score → score_snapshot
  │ evaluates alert rules → alert_events
  │ invalidates Redis cache for this symbol
  ▼
API / Grafana read pre-computed results
```

---

## Testing Event-Driven Code

```python
# tests/unit/test_streams.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_publish_task_adds_to_stream():
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = b"1234567890-0"

    msg_id = await publish_task(mock_redis, "tasks:ingest", {"type": "daily_prices", "symbol": "AAPL"})

    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == "tasks:ingest"
    assert "payload" in call_args[0][1]

@pytest.mark.asyncio
async def test_worker_acknowledges_on_success():
    mock_redis = AsyncMock()
    mock_redis.xreadgroup.side_effect = [
        [],  # no pending
        [("tasks:ingest", [("msg-1", {b"payload": b'{"type":"daily_prices","symbol":"AAPL"}'})])]
    ]
    mock_process = AsyncMock()

    # Simulate one iteration of the worker loop
    messages = await consume_stream(mock_redis, "tasks:ingest", "ingester-workers", "w1")
    for msg_id, payload in messages:
        await mock_process(payload)
        await acknowledge(mock_redis, "tasks:ingest", "ingester-workers", msg_id)

    mock_redis.xack.assert_called_once_with("tasks:ingest", "ingester-workers", "msg-1")
```
