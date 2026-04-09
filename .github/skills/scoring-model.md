---
name: scoring-model
description: Weighted composite scoring formula, configurable weights, and action thresholds for the stocklens system.
---

# Scoring Model

## Composite Score Formula

```
rising_stock_score =
  0.20 * growth_acceleration_score  (EPS + revenue acceleration combined)
  0.15 * margin_expansion_score     (gross + operating margin delta)
  0.20 * relative_strength_score    (weighted 1M/3M/6M RS vs benchmark)
  0.10 * unusual_volume_score       (volume ratio, direction-adjusted)
  0.10 * estimate_revision_score    (analyst upward revisions)
  0.05 * insider_score              (net insider buying)
  0.10 * backlog_demand_score       (book-to-bill, backlog growth — if available)
  0.10 * valuation_quality_score    (valuation + quality composite)
```

Final score normalized to **[-100, 100]**:
- Positive = bullish
- Negative = bearish
- 0 = neutral / insufficient data

## Weight Configuration

Weights are stored in `backend/app/config/scoring_weights.yaml` — never hardcoded:

```yaml
# scoring_weights.yaml
version: 1
weights:
  growth_acceleration: 0.20
  margin_expansion: 0.15
  relative_strength: 0.20
  unusual_volume: 0.10
  estimate_revision: 0.10
  insider: 0.05
  backlog_demand: 0.10
  valuation_quality: 0.10

# Horizon adjustments (multiplied on top of base weights)
long_term:
  growth_acceleration: 1.3
  margin_expansion: 1.2
  relative_strength: 0.8
  unusual_volume: 0.5

short_term:
  relative_strength: 1.4
  unusual_volume: 1.5
  growth_acceleration: 0.7
  margin_expansion: 0.6
```

## Action Thresholds

```python
THRESHOLDS = [
    (60,  "strong_buy"),
    (25,  "buy"),
    (-25, "hold"),
    (-60, "sell"),
    (-100,"strong_sell"),
]

def score_to_action(score: float) -> str:
    for threshold, action in THRESHOLDS:
        if score >= threshold:
            return action
    return "strong_sell"
```

## Sub-Score Normalization

Each factor must be normalized to [-1.0, 1.0] before weighting:

```python
def normalize_growth(raw_growth: float) -> float:
    """Map growth rate to [-1, 1]. 50%+ growth = 1.0."""
    return max(-1.0, min(1.0, raw_growth / 0.5))

def normalize_rs(rs: float) -> float:
    """Relative strength: >1 = outperforming. Map to [-1, 1]."""
    return max(-1.0, min(1.0, (rs - 1.0) * 5))  # 20% outperformance = 1.0

def normalize_rsi(rsi: float) -> float:
    """RSI: oversold (<30) = bullish, overbought (>70) = bearish."""
    if rsi < 30:
        return (30 - rsi) / 30           # 0 RSI = 1.0, 30 RSI = 0.0
    elif rsi > 70:
        return -(rsi - 70) / 30          # 100 RSI = -1.0, 70 RSI = 0.0
    return 0.0  # neutral zone
```

## Confidence

```python
confidence = observed_factor_weight / total_possible_weight
# Clamped to [0, 1]
# Low confidence = few factors available (e.g. new stock, missing fundamentals)
```

## Score Storage

```sql
-- score_snapshot
symbol, as_of_date, horizon,   -- 'long_term' or 'short_term'
score, action, confidence,
weight_version,                 -- which scoring_weights.yaml version was used
factor_contributions JSONB,     -- {factor_name: contribution_value} for explainability
created_at
```

Always store `factor_contributions` so a user can understand why a stock scored high.
