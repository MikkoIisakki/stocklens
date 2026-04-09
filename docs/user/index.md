# Stocklens

Stock screening system for **US** (S&P 500 top + Nasdaq tech) and **Finnish** (Helsinki exchange) markets.

!!! note "Investment disclaimer"
    Stocklens is a **screening and ranking tool**, not investment advice.
    All output is for informational purposes only. Always do your own research
    before making any investment decision.

## What it does

- Ingests end-of-day prices daily from Yahoo Finance
- Stores a full price history with audit trail
- Exposes a REST API to query assets and price history
- (Phase 2) Computes factor signals and composite scores
- (Phase 3) Fires alerts when scores cross thresholds

## Quick links

| | |
|---|---|
| [Getting Started](getting-started.md) | Install, run, first query |
| [API Reference](api-reference.md) | Endpoint documentation |
| [Architecture](architecture.md) | How the system is structured |
| [Data Sources](data-sources.md) | What data we use and its limitations |
| [Operations](operations.md) | `make` targets, health check, scheduler |

## Current status

The system is in **Phase 1 — Data Foundation**.
Price ingestion for US and Finnish markets is operational.
Factor signals and scoring are planned for Phase 2.
