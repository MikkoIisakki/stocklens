---
name: factor-engineering
description: How to compute each factor/signal used in the pulse scoring model. Formulas, data requirements, and interpretation for both long-term and short-term signals. For engineer use — consult analyst agent for the investment thesis behind each factor.
---

# Factor Engineering

> **Note for engineer**: This skill covers *how* to compute factors. For *why* each factor is included and the investment thesis behind it, see the `analyst` agent and the `factor-research` skill. Do not change factor definitions or thresholds without analyst approval.

All factors are stored in `factor_snapshot` with `(symbol, as_of_date)`. Compute only for assets with updated source data (delta-first).

## Long-Term Factors

### Revenue Growth YoY
```python
revenue_growth_yoy = (revenue_ttm - revenue_ttm_1y_ago) / abs(revenue_ttm_1y_ago)
```
Bullish if > 0.15 (15% growth). Source: income statement quarterly data.

### Revenue Growth Acceleration
```python
growth_q_now = (revenue_q_latest - revenue_q_1y_ago) / abs(revenue_q_1y_ago)
growth_q_prev = (revenue_q_prev - revenue_q_2y_ago) / abs(revenue_q_2y_ago)
acceleration = growth_q_now - growth_q_prev
```
Bullish if acceleration > 0. Decelerating growth is a warning sign even if still positive.

### EPS Growth YoY
```python
eps_growth_yoy = (eps_ttm - eps_ttm_1y_ago) / abs(eps_ttm_1y_ago)
```

### EPS Growth Acceleration
Same pattern as revenue acceleration but for EPS. Most important single factor for rising stocks.

### Gross Margin Expansion
```python
margin_delta = gross_margin_latest_quarter - gross_margin_4q_ago
```
Bullish if > 0. Shrinking margins on rising revenue is a red flag.

### Operating Margin Delta
Same as gross margin but for operating income / revenue.

### Return on Equity (ROE)
```python
roe = net_income_ttm / shareholders_equity
```
Bullish if > 0.15. Compare within sector.

### Valuation Score
Composite of:
- P/E ratio vs sector median (lower = more attractive)
- P/S ratio for high-growth companies (P/E meaningless if negative earnings)
- PEG ratio = P/E / EPS growth rate (< 1.0 is attractive)

```python
# Normalize each to 0-1, invert so lower valuation = higher score
pe_score = 1 - min(pe_ratio / 50, 1.0)  # cap at 50x
peg_score = 1 - min(peg_ratio / 2, 1.0) if peg_ratio > 0 else 0.5
valuation_score = 0.5 * pe_score + 0.5 * peg_score
```

### Quality Score
```python
# Composite of debt safety and cash generation
debt_to_equity_score = 1 - min(debt_to_equity / 2.0, 1.0)
current_ratio_score = min(current_ratio / 2.0, 1.0)
fcf_yield = free_cash_flow / market_cap
fcf_score = min(fcf_yield / 0.05, 1.0)  # 5% FCF yield = full score
quality_score = (debt_to_equity_score + current_ratio_score + fcf_score) / 3
```

---

## Short-Term Factors

### Relative Strength
```python
# Price return vs benchmark (SPY for US, OMX Helsinki for FI)
rs_1m = (price_now / price_1m_ago) / (benchmark_now / benchmark_1m_ago)
rs_3m = (price_now / price_3m_ago) / (benchmark_now / benchmark_3m_ago)
rs_6m = (price_now / price_6m_ago) / (benchmark_now / benchmark_6m_ago)
```
Bullish if rs > 1.0 (outperforming benchmark). Weight: rs_1m 0.5, rs_3m 0.3, rs_6m 0.2.

### RSI (14-day)
```python
# Use pandas-ta: df.ta.rsi(length=14)
```
- < 30: oversold (potential buy)
- > 70: overbought (caution)
- For trending stocks, 40–80 range is normal — don't sell just because RSI > 70

### MACD Crossover
```python
# Use pandas-ta: df.ta.macd(fast=12, slow=26, signal=9)
# Bullish: MACD line crosses above signal line
# Bearish: MACD line crosses below signal line
```

### EMA Cross (short-term trend)
```python
ema_20 = df.ta.ema(length=20)
ema_50 = df.ta.ema(length=50)
# Bullish: ema_20 > ema_50 (golden cross territory)
# Bearish: ema_20 < ema_50 (death cross territory)
```

### Unusual Volume
```python
avg_volume_20d = df['Volume'].rolling(20).mean()
volume_ratio = df['Volume'].iloc[-1] / avg_volume_20d.iloc[-1]
# Bullish if > 2.0 and price up; bearish if > 2.0 and price down
```

### Breakout Signal
```python
high_52w = df['High'].rolling(252).max()
is_52w_breakout = df['Close'].iloc[-1] > high_52w.iloc[-2]  # broke through yesterday's 52w high
```

---

## Factor Storage

```sql
-- factor_snapshot columns (one row per symbol per date)
symbol, as_of_date,
revenue_growth_yoy, revenue_growth_acceleration,
eps_growth_yoy, eps_growth_acceleration,
gross_margin_delta, operating_margin_delta,
roe, valuation_score, quality_score,
relative_strength_1m, relative_strength_3m, relative_strength_6m,
rsi_14, macd_signal,   -- 'bullish' / 'bearish' / 'neutral'
ema_cross_signal,
unusual_volume_ratio,
is_52w_breakout,
analyst_revision_score,  -- populated from Finnhub when available
insider_buy_score        -- populated from events table
```

## Using pandas-ta

```python
import pandas_ta as ta

# Attach to DataFrame
df.ta.rsi(length=14, append=True)      # adds RSI_14 column
df.ta.macd(fast=12, slow=26, signal=9, append=True)  # adds MACD_12_26_9, MACDh, MACDs
df.ta.ema(length=20, append=True)
df.ta.bbands(length=20, append=True)   # Bollinger Bands
df.ta.obv(append=True)                 # On-Balance Volume
df.ta.atr(length=14, append=True)      # Average True Range
```
