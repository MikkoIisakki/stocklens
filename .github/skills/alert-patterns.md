---
name: alert-patterns
description: Alert rule definition, threshold evaluation, deduplication, and delivery patterns for the pulse system.
---

# Alert Patterns

## Alert Rule Schema

```sql
CREATE TABLE alert_rule (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    symbol      TEXT REFERENCES asset(symbol),  -- NULL = applies to all assets
    market      TEXT,                            -- 'US', 'FI', or NULL for all
    metric      TEXT NOT NULL,   -- 'score', 'rsi_14', 'price_change_1d', 'volume_ratio', 'score_action'
    operator    TEXT NOT NULL,   -- 'gt', 'lt', 'gte', 'lte', 'eq', 'crosses_above', 'crosses_below'
    threshold   NUMERIC NOT NULL,
    horizon     TEXT,            -- 'long_term', 'short_term', NULL for both
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE alert_event (
    id          BIGSERIAL PRIMARY KEY,
    rule_id     BIGINT NOT NULL REFERENCES alert_rule(id),
    symbol      TEXT NOT NULL REFERENCES asset(symbol),
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric      TEXT NOT NULL,
    value       NUMERIC NOT NULL,
    threshold   NUMERIC NOT NULL,
    message     TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE
);
```

## Example Alert Rules

```sql
-- Notify when any stock crosses into strong_buy
INSERT INTO alert_rule (name, metric, operator, threshold)
VALUES ('Strong buy signal', 'score', 'gte', 60);

-- RSI oversold for specific stock
INSERT INTO alert_rule (name, symbol, metric, operator, threshold)
VALUES ('AAPL oversold', 'AAPL', 'rsi_14', 'lte', 30);

-- Unusual volume spike (any US stock)
INSERT INTO alert_rule (name, market, metric, operator, threshold)
VALUES ('US volume spike', 'US', 'volume_ratio', 'gte', 2.5);

-- Score drops from buy to hold (crosses below threshold)
INSERT INTO alert_rule (name, metric, operator, threshold)
VALUES ('Score deterioration', 'score', 'crosses_below', 25);
```

## Alert Evaluation Logic

```python
async def evaluate_alerts(conn, as_of_date: date):
    rules = await get_active_rules(conn)
    for rule in rules:
        # Get candidate assets
        symbols = await get_symbols_for_rule(conn, rule)
        for symbol in symbols:
            current_value = await get_metric_value(conn, symbol, rule.metric, as_of_date)
            prev_value = await get_metric_value(conn, symbol, rule.metric, as_of_date - timedelta(days=1))

            triggered = evaluate_condition(rule.operator, current_value, prev_value, rule.threshold)

            if triggered:
                # Deduplication: don't fire same rule+symbol more than once per day
                already_fired = await check_recent_alert(conn, rule.id, symbol, as_of_date)
                if not already_fired:
                    await create_alert_event(conn, rule, symbol, current_value)
```

## Condition Evaluation

```python
def evaluate_condition(operator: str, current: float, previous: float, threshold: float) -> bool:
    match operator:
        case "gt":            return current > threshold
        case "lt":            return current < threshold
        case "gte":           return current >= threshold
        case "lte":           return current <= threshold
        case "eq":            return current == threshold
        case "crosses_above": return previous < threshold <= current
        case "crosses_below": return previous > threshold >= current
        case _:               raise ValueError(f"Unknown operator: {operator}")
```

## Deduplication

```sql
-- Check if rule already fired for this symbol today
SELECT 1 FROM alert_event
WHERE rule_id = $1
  AND symbol = $2
  AND triggered_at::date = $3
LIMIT 1;
```

## Supported Metrics

| Metric | Source table | Column |
|---|---|---|
| `score` | `score_snapshot` | `score` |
| `rsi_14` | `factor_snapshot` | `rsi_14` |
| `volume_ratio` | `factor_snapshot` | `unusual_volume_ratio` |
| `price_change_1d` | `daily_price` | computed: `(close - prev_close) / prev_close` |
| `relative_strength_1m` | `factor_snapshot` | `relative_strength_1m` |
| `score_action` | `score_snapshot` | `action` (string comparison) |

## Alert API Endpoints

```
GET  /v1/alerts/events          — list unacknowledged alert events, newest first
POST /v1/alerts/events/{id}/ack — acknowledge an event
GET  /v1/alerts/rules           — list all rules
POST /v1/alerts/rules           — create a rule
PUT  /v1/alerts/rules/{id}      — update a rule
DEL  /v1/alerts/rules/{id}      — deactivate a rule
```
