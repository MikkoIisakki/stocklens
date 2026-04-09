---
name: factor-research
description: Academic and practitioner evidence behind each factor used in the pulse scoring model. Provides the research basis for factor adoption, weighting, and retirement decisions.
---

# Factor Research

This skill documents the evidence base for every factor in the scoring model. The analyst agent uses this to justify factor selection and weighting. Before adopting or retiring a factor, there must be an entry here.

---

## Earnings Momentum (EPS Acceleration)

**Evidence strength: Very strong**

- Jegadeesh & Titman (1993) — *Returns to Buying Winners and Selling Losers* — documented 12-month price momentum persistence, partly explained by slow incorporation of earnings information
- Ball & Brown (1968) — *An Empirical Evaluation of Accounting Income Numbers* — showed post-earnings announcement drift (PEAD): markets underreact to earnings surprises, continuing to drift in the surprise direction for weeks
- Chan, Jegadeesh & Lakonishok (1996) — *Momentum Strategies* — earnings momentum and price momentum are complementary; combining them outperforms either alone
- IBD research (O'Neil): stocks making new highs had accelerating EPS in the prior 2–3 quarters in ~75% of the biggest winners studied

**Practitioner consensus**: EPS acceleration is the single most cited factor among growth investors (CAN SLIM, Driehaus, IBD). The mechanism is behavioral: analysts and investors are slow to revise models upward when a trend is improving.

**Failure mode**: Works poorly in sectors where EPS is not meaningful (pre-revenue biotech, SPACs) or where accounting choices make EPS manipulation easy. Strong in technology, consumer, and industrials.

---

## Price Momentum (Relative Strength)

**Evidence strength: Very strong**

- Jegadeesh & Titman (1993) — 12-month price momentum (skipping last month) generates significant abnormal returns
- Asness, Moskowitz & Pedersen (2013) — *Value and Momentum Everywhere* — momentum works across asset classes, countries, and time periods; among the most replicated findings in finance
- Fama & French (2012) — reluctantly acknowledged momentum as a pervasive anomaly despite not fitting their original model
- Daniel & Moskowitz (2016) — momentum crashes in bear market reversals; important failure mode

**Lookback window**: 12-month return (skipping last month) is academically canonical. For practical use, 3–6 month RS is more actionable with less crash risk. We use 1M/3M/6M blend.

**Failure mode**: Momentum crashes are real — after prolonged bear markets, strong momentum reverses sharply. In the current algorithm this is the most dangerous factor in market downturns. Regime detection (Phase 4) would mitigate this.

---

## Analyst Estimate Revisions

**Evidence strength: Strong**

- Stickel (1991) — *Common Stock Returns Surrounding Earnings Forecast Revisions* — upward EPS revisions predict positive abnormal returns over the following month
- Lys & Sohn (1990) — analyst revisions have information content beyond what's already in prices
- Empirical: consensus estimate increases are correlated with institutional activity (they often have the same information source)

**Why it works**: Analysts revise estimates when they receive new information (management calls, industry data, supply chain checks). Retail investors are the last to see this information.

**Failure mode**: Analyst herding — analysts revise together, so the signal captures consensus, not alpha. Works better when revisions are sparse (few analysts covering = less herding). Coverage gap for Finnish small-caps makes this signal unreliable in the FI universe.

---

## Revenue Growth and Acceleration

**Evidence strength: Moderate-Strong**

- Lakonishok, Shleifer & Vishny (1994) — *Contrarian Investment, Extrapolation and Risk* — high sales growth alone is often over-extrapolated by the market; acceleration is the key distinction
- Sloan (1996) — *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows?* — revenue quality (cash-backed) predicts future returns better than accrual-based earnings

**Practical note**: Revenue growth is harder to manipulate than EPS but easier than FCF. Use it to validate EPS acceleration — EPS growing while revenue declines = red flag.

---

## Gross Margin Expansion

**Evidence strength: Moderate**

- Novy-Marx (2013) — *The Other Side of Value: The Gross Profitability Premium* — gross profitability (gross profit / assets) predicts returns as strongly as book-to-market; expanding margins amplify this

**Mechanism**: Margin expansion signals either pricing power (demand exceeds supply) or improving unit economics (scale benefits). Both indicate competitive position strengthening.

**Failure mode**: Cyclical margin expansion (commodity input cost tailwinds) reverses; only structural margin expansion is sustained. The signal is noisy quarter-to-quarter; use a 4-quarter comparison to smooth.

---

## Quality Factors (ROE, FCF, Debt)

**Evidence strength: Strong**

- Piotroski (2000) — *Value Investing: The Use of Historical Financial Statement Information* — F-Score (9-point quality checklist) generated 23% annual spread between high and low quality value stocks
- Novy-Marx (2013) — gross profitability premium: profitable firms outperform unprofitable ones even after controlling for valuation
- Asness, Frazzini & Pedersen (2019) — *Quality Minus Junk* — long high-quality, short low-quality generates persistent risk-adjusted returns; quality defined as profitability + growth + safety + payout
- Buffett/Munger framework: ROIC sustainably above cost of capital = durable value creation

**What "quality" means in our model**: FCF generation (not accounting profit), manageable debt, stable returns on capital. These protect against blow-ups more than they predict outperformance.

---

## Unusual Volume

**Evidence strength: Moderate**

- Blume, Easley & O'Hara (1994) — *Market Statistics and Technical Analysis: The Role of Volume* — volume carries information about the quality of price signals; price moves on high volume are more persistent
- Gervais, Kaniel & Mingelgrin (2001) — *The High-Volume Return Premium* — stocks with unusually high volume over a week subsequently outperform

**Mechanism**: Institutional investors are large; they cannot hide their activity. Unusual volume is a proxy for informed buying.

**Failure mode**: Index rebalancing, options expiration, ETF creation/redemption, short squeezes all generate volume that is not informative. The signal is noisiest on quarterly expiration dates.

---

## Valuation (PEG Ratio)

**Evidence strength: Moderate (as a combined factor)**

- Fama & French (1992) — *The Cross-Section of Expected Stock Returns* — value (low P/B) outperforms growth over long periods
- O'Neil / IBD: valuation is a secondary factor for growth stocks; overpaying is a risk but excessive cheapness often signals problems
- Damodaran: PEG < 1.0 identifies stocks where price doesn't reflect growth rate; useful screen but not a standalone signal

**Important caveat**: Valuation is a poor timing signal — cheap stocks can get cheaper; expensive stocks can get more expensive for years. Used as a filter (avoid extreme overvaluation) rather than a primary signal in our model.

**Weight justification (0.10)**: Lower weight because high-quality growth stocks often appear expensive on traditional metrics (Amazon, 2010–2020). Removing the most overvalued names is valuable; but don't screen out every stock with P/E > 30.

---

## Factors Under Consideration (Not Yet Adopted)

These require analyst specification and backtest validation before inclusion:

| Factor | Thesis | Research basis | Concern |
|---|---|---|---|
| Insider buying | Management knows their company best | Seyhun (1998): insider buys predict 6-month returns | Data quality on free sources; noise from option exercises |
| Short interest decline | Short sellers covering = negative thesis abandoned | Dechow et al. (2001): high short interest predicts underperformance | Free data limited; contrarian signal only in extremes |
| 52-week high breakout | Anchoring bias — investors fixate on this level | George & Hwang (2004): 52-week high proximity predicts momentum | False breakouts common; volume confirmation required |
| Earnings quality (accruals) | Low accruals = cash-backed earnings | Sloan (1996): low accrual firms outperform | Requires detailed cash flow parsing; data heavy |
| Sector momentum | Rotate into leading sectors | Moskowitz & Grinblatt (1999): industry momentum explains much of stock momentum | Reduces stock-picking signal to sector bet |

---

## Backtest Criteria for Factor Validation

Before any factor changes weights or a new factor is adopted, the backtest must demonstrate:

1. **IC (Information Coefficient) > 0.05** — Spearman correlation between factor value and subsequent 3-month return, average across the test period
2. **Positive across sub-periods** — the factor must work in at least 3 of 4 market regimes tested (bull, bear, high-vol, low-vol)
3. **US and FI tested separately** — a factor valid for US growth stocks may not apply to Helsinki industrials
4. **Decay analysis** — IC at 1M, 3M, 6M lookforward; a factor with high 1M but zero 6M IC is a short-term signal, not long-term
5. **Transaction cost adjusted** — high-turnover signals must survive realistic bid-ask spreads

A factor that fails these criteria is rejected regardless of theoretical appeal.
