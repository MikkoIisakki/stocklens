---
name: investment-analysis
description: Fundamental and technical analysis theory, market mechanics, and stock selection frameworks that underpin the pulse algorithm. Reference for the analyst agent.
---

# Investment Analysis

## Two Schools — Why Both Matter

The pulse combines both approaches because neither is sufficient alone:

- **Fundamental analysis** tells you *what* to buy — companies with improving business quality
- **Technical analysis** tells you *when* to buy — when the market is confirming the thesis with price and volume

A fundamentally improving business bought at the wrong time (e.g. into a sector rotation out of tech) can sit flat for months. Strong price action without improving fundamentals is speculation. The composite score requires both to fire before a strong buy signal is generated.

---

## Fundamental Analysis

### What Drives Long-Term Stock Prices

Over the long run, stock prices follow earnings. The market is a forward-looking earnings discounting machine. Permanent outperformance comes from:

1. **Earnings growth** — companies that grow earnings faster than expected
2. **Earnings quality** — growth backed by real cash flow, not accounting games
3. **Competitive advantage (moat)** — ability to sustain high returns on capital

### Key Metrics and What They Mean

#### Earnings Per Share (EPS)
- **Trailing EPS**: past 12 months actual earnings per share
- **Forward EPS**: analyst consensus estimate for next 12 months
- **EPS growth YoY**: `(EPS_now - EPS_1yr_ago) / abs(EPS_1yr_ago)` — directional
- **EPS acceleration**: change in the *rate* of growth — the most predictive metric

#### Revenue
- Top-line growth is harder to fake than earnings
- Revenue deceleration while EPS grows = cost-cutting, not organic strength
- **Organic revenue growth** (excluding acquisitions and FX) is the cleanest signal

#### Margins
- **Gross margin**: `(revenue - COGS) / revenue` — product economics
- **Operating margin**: `operating_income / revenue` — business efficiency
- **Net margin**: `net_income / revenue` — after tax and interest
- Expanding margins = pricing power or operating leverage; contracting = cost pressure or competition

#### Return on Equity (ROE)
- `net_income / shareholders_equity`
- Measures how efficiently management uses equity capital
- > 15% is generally attractive; compare within sector
- **DuPont decomposition**: ROE = (net margin) × (asset turnover) × (leverage) — use to understand *why* ROE is high

#### Return on Invested Capital (ROIC)
- `NOPAT / invested_capital` (Net Operating Profit After Tax / debt + equity)
- Better than ROE because it accounts for debt
- ROIC > WACC (cost of capital) = value creation; ROIC < WACC = value destruction

#### Free Cash Flow (FCF)
- `operating_cash_flow - capital_expenditure`
- Earnings can be managed; cash is harder to fake
- **FCF yield**: `FCF / market_cap` — like a dividend yield but from cash generation

#### Valuation Ratios
| Ratio | Formula | Use when | Caution |
|---|---|---|---|
| P/E | price / EPS | Profitable companies | Meaningless if EPS < 0 |
| PEG | P/E / EPS_growth_rate | Growth companies | Requires reliable growth estimate |
| P/S | price / revenue_per_share | Pre-profit or low-margin | Ignores profitability |
| P/FCF | price / FCF_per_share | Cash-generative businesses | CapEx-heavy businesses look cheap |
| EV/EBITDA | enterprise_value / EBITDA | Capital structure comparison | Ignores CapEx quality |

#### Balance Sheet Health
- **Debt-to-equity**: total_debt / shareholders_equity — < 1.0 generally safe
- **Current ratio**: current_assets / current_liabilities — > 1.5 comfortable
- **Interest coverage**: EBIT / interest_expense — > 5x comfortable
- High debt + decelerating revenue = danger zone

---

## Technical Analysis

### Why Price and Volume Carry Information

Markets are not perfectly efficient in the short term. Price and volume patterns reflect the aggregate behavior of all market participants — including institutional investors with information advantages. Monitoring price action captures:

- **Institutional accumulation** — large buyers can't hide their activity; volume rises as they build positions
- **Relative strength** — stocks that hold up during market weakness or outperform during rallies have institutional support
- **Breakouts** — price crossing resistance levels often precedes a new price discovery phase

### Key Technical Concepts

#### Trend
- **Uptrend**: series of higher highs and higher lows
- **Downtrend**: series of lower highs and lower lows
- **Moving averages** (EMA 20, EMA 50, EMA 200) smooth noise and reveal trend direction
- **Golden cross**: EMA 20 crosses above EMA 50 — bullish trend signal
- **Death cross**: EMA 20 crosses below EMA 50 — bearish trend signal

#### Relative Strength (RS)
- Compares a stock's performance to a benchmark over a period
- RS > 1.0 = outperforming; RS < 1.0 = underperforming
- Stocks with sustained RS > 1.0 attract institutional buying
- IBD (Investor's Business Daily) RS Rating: stocks in the top 20% of 12-month RS have historically outperformed

#### RSI (Relative Strength Index, 14-day)
- Oscillator 0–100 measuring speed of price changes
- < 30: oversold (potential reversal up) — stronger signal when combined with positive fundamentals
- > 70: overbought (potential reversal down) — in strong uptrends, RSI 40–80 is normal
- **Divergence**: price makes new high but RSI doesn't — bearish warning

#### MACD (Moving Average Convergence Divergence)
- `MACD line = EMA(12) - EMA(26)`; `Signal line = EMA(9) of MACD`
- **Bullish crossover**: MACD crosses above signal line
- **Bearish crossover**: MACD crosses below signal line
- **Histogram**: MACD - Signal — shows momentum strength

#### Volume Analysis
- Price moves on above-average volume are more significant
- **On-Balance Volume (OBV)**: cumulative volume indicator — rising OBV = accumulation
- **Volume spike on breakout**: validates the move; spike on rejection = distribution

#### Support and Resistance
- **Support**: price level where buyers historically step in
- **Resistance**: price level where sellers historically step in
- **Breakout**: price closing above resistance on high volume — often the start of a new leg up
- **52-week high breakout**: stocks making new all-time or 52-week highs often continue higher (counter-intuitive but empirically supported)

---

## Stock Selection Frameworks

### CAN SLIM (William O'Neil, IBD)
Evidence-based growth stock selection framework. Most of our long-term factors derive from it:

| Letter | Factor | Our equivalent |
|---|---|---|
| C | Current quarterly EPS growth > 25% | EPS growth YoY |
| A | Annual EPS growth > 25% for 3 years | EPS acceleration |
| N | New product, CEO, or 52-week high | Breakout signal |
| S | Supply/demand — low float + high volume | Unusual volume ratio |
| L | Leader — top RS in its sector | Relative strength |
| I | Institutional sponsorship | Analyst revision + volume |
| M | Market direction — buy only in uptrends | Macro/sector momentum |

### Quality + Momentum (Factor Investing)
Academic factor research shows that combining **quality** (high ROE, low debt, stable earnings) with **momentum** (past 6-12 month price return) produces persistent risk-adjusted outperformance:
- Quality alone: avoids blow-ups, moderate returns
- Momentum alone: high returns but volatile, suffers in regime changes
- Combined: better Sharpe ratio than either alone

### Mean Reversion vs Momentum
- **Short-term (days)**: mean reversion dominates — don't buy after large single-day spikes
- **Medium-term (1–12 months)**: momentum dominates — buy what's working
- **Long-term (> 1 year)**: mean reversion returns — valuation matters again
- The pulse targets the medium-term momentum window primarily

---

## Market Regimes

Algorithm performance varies by market environment. Be aware of these regimes:

| Regime | Characteristics | Impact on signals |
|---|---|---|
| Bull market, early | Breadth expanding, all sectors up | Most signals work well |
| Bull market, late | Narrow leadership, defensive outperform | RS signal narrows; quality matters more |
| Bear market | Downtrend, risk-off | Most signals fail; cash is a position |
| High inflation | Rate-sensitive growth stocks punished | Valuation multiple compression; value works better |
| Low rate environment | Growth stocks rewarded | PEG ratios expand; momentum works well |
| Sector rotation | Capital moves between sectors rapidly | RS signal is noisy; short lookbacks preferred |

The algorithm does not currently account for market regime. Regime detection is a Phase 4 enhancement.
