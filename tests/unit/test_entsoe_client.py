"""Unit tests for the ENTSO-E Transparency Platform day-ahead client.

The client returns rows shaped per the interval-based platform convention
(ADR-005) so ``app.normalization.energy_price.normalize_day_ahead_response``
can persist them directly:

    {
        "deliveryDate": "YYYY-MM-DD",
        "currency": "EUR",
        "rows": [
            {"interval_start": <datetime UTC>,
             "interval_end":   <datetime UTC>,
             "interval_minutes": 15 | 60 | ...,
             "value": <float>},
            ...
        ],
    }

All HTTP calls are mocked with respx — no real network traffic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from app.ingestion.entsoe_client import (
    REGION_TO_EIC,
    EntsoeAuthError,
    EntsoeNoDataError,
    fetch_day_ahead,
)

ENTSOE_HOST = "web-api.tp.entsoe.eu"


def _build_xml(prices: list[float], resolution: str = "PT60M") -> str:
    """Build a minimal valid ENTSO-E A44 Publication_MarketDocument.

    One TimeSeries with one Period containing one Point per supplied price.
    Resolution is configurable so tests can exercise PT60M and PT15M.
    """
    points = "\n".join(
        f"<Point><position>{i + 1}</position><price.amount>{p}</price.amount></Point>"
        for i, p in enumerate(prices)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
  <TimeSeries>
    <Period>
      <timeInterval>
        <start>2025-01-15T00:00Z</start>
        <end>2025-01-16T00:00Z</end>
      </timeInterval>
      <resolution>{resolution}</resolution>
      {points}
    </Period>
  </TimeSeries>
</Publication_MarketDocument>"""


def _empty_xml() -> str:
    """ENTSO-E returns an Acknowledgement_MarketDocument with reason 'No matching data found'."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Acknowledgement_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:8:1">
  <Reason>
    <code>999</code>
    <text>No matching data found</text>
  </Reason>
</Acknowledgement_MarketDocument>"""


# ─── Region/EIC mapping ───────────────────────────────────────────────────────


def test_region_to_eic_covers_all_seeded_regions() -> None:
    assert REGION_TO_EIC["FI"] == "10YFI-1--------U"
    assert REGION_TO_EIC["SE3"] == "10Y1001A1001A46L"
    assert REGION_TO_EIC["SE4"] == "10Y1001A1001A47J"
    assert REGION_TO_EIC["EE"] == "10Y1001A1001A39I"
    assert REGION_TO_EIC["LT"] == "10YLT-1001A0008Q"
    assert REGION_TO_EIC["LV"] == "10YLV-1001A00074"


# ─── Query construction ──────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_builds_correct_query_params() -> None:
    captured: dict[str, str] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, text=_build_xml([10.0] * 24))

    respx.route(host=ENTSOE_HOST).mock(side_effect=_capture)

    await fetch_day_ahead(date(2025, 1, 15), region="FI", token="abc-token")

    assert captured["securityToken"] == "abc-token"
    assert captured["documentType"] == "A44"
    assert captured["in_Domain"] == "10YFI-1--------U"
    assert captured["out_Domain"] == "10YFI-1--------U"
    assert captured["periodStart"] == "202501150000"
    assert captured["periodEnd"] == "202501160000"


@respx.mock
@pytest.mark.asyncio
async def test_unknown_region_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        await fetch_day_ahead(date(2025, 1, 15), region="ZZ", token="t")


# ─── Response parsing — PT60M (hourly) ───────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_pt60m_returns_24_rows_for_normal_day() -> None:
    prices = [50.0 + h for h in range(24)]
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    assert result["currency"] == "EUR"
    assert result["deliveryDate"] == "2025-01-15"
    assert len(result["rows"]) == 24
    assert all(r["interval_minutes"] == 60 for r in result["rows"])


@respx.mock
@pytest.mark.asyncio
async def test_pt60m_row_shape_matches_interval_contract() -> None:
    respx.route(host=ENTSOE_HOST).mock(
        return_value=httpx.Response(200, text=_build_xml([42.5] * 24))
    )

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    first = result["rows"][0]
    assert first["interval_start"] == datetime(2025, 1, 15, 0, 0, tzinfo=UTC)
    assert first["interval_end"] == datetime(2025, 1, 15, 1, 0, tzinfo=UTC)
    assert first["interval_minutes"] == 60
    assert first["value"] == 42.5

    last = result["rows"][23]
    assert last["interval_start"] == datetime(2025, 1, 15, 23, 0, tzinfo=UTC)
    assert last["interval_end"] == datetime(2025, 1, 16, 0, 0, tzinfo=UTC)


# ─── Response parsing — PT15M (quarter-hourly) ───────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_pt15m_returns_96_rows_for_normal_day() -> None:
    """Nordic/Baltic zones now publish 15-minute resolution; the client must preserve it."""
    prices = [10.0 + i * 0.1 for i in range(96)]
    respx.route(host=ENTSOE_HOST).mock(
        return_value=httpx.Response(200, text=_build_xml(prices, resolution="PT15M"))
    )

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    assert len(result["rows"]) == 96
    assert all(r["interval_minutes"] == 15 for r in result["rows"])


@respx.mock
@pytest.mark.asyncio
async def test_pt15m_intervals_are_15_minutes_apart() -> None:
    prices = [10.0] * 96
    respx.route(host=ENTSOE_HOST).mock(
        return_value=httpx.Response(200, text=_build_xml(prices, resolution="PT15M"))
    )

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    first = result["rows"][0]
    second = result["rows"][1]
    last = result["rows"][95]
    assert first["interval_start"] == datetime(2025, 1, 15, 0, 0, tzinfo=UTC)
    assert first["interval_end"] == datetime(2025, 1, 15, 0, 15, tzinfo=UTC)
    assert second["interval_start"] == datetime(2025, 1, 15, 0, 15, tzinfo=UTC)
    assert last["interval_start"] == datetime(2025, 1, 15, 23, 45, tzinfo=UTC)
    assert last["interval_end"] == datetime(2025, 1, 16, 0, 0, tzinfo=UTC)


# ─── Negative-price preservation ─────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_negative_prices_preserved() -> None:
    prices = [-15.0] + [10.0] * 23
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    assert result["rows"][0]["value"] == -15.0


# ─── Error handling ──────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_http_401_raises_auth_error() -> None:
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(401, text="Unauthorized"))

    with pytest.raises(EntsoeAuthError):
        await fetch_day_ahead(date(2025, 1, 15), region="FI", token="bad")


@respx.mock
@pytest.mark.asyncio
async def test_empty_acknowledgement_raises_no_data_error() -> None:
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_empty_xml()))

    with pytest.raises(EntsoeNoDataError):
        await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")


# ─── DST behaviour (documents the chosen contract) ───────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_dst_spring_forward_returns_23_rows_pt60m() -> None:
    """On EU spring-forward day at PT60M, ENTSO-E publishes 23 hourly points; client returns 23."""
    prices = [40.0] * 23
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 3, 30), region="FI", token="t")

    assert len(result["rows"]) == 23


@respx.mock
@pytest.mark.asyncio
async def test_dst_fall_back_returns_25_rows_pt60m() -> None:
    """On EU autumn fall-back day at PT60M, ENTSO-E publishes 25 hourly points; client returns 25."""
    prices = [40.0] * 25
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 10, 26), region="FI", token="t")

    assert len(result["rows"]) == 25


@respx.mock
@pytest.mark.asyncio
async def test_dst_spring_forward_returns_92_rows_pt15m() -> None:
    """At PT15M a 23-hour day is 92 quarter-hour slots."""
    prices = [40.0] * 92
    respx.route(host=ENTSOE_HOST).mock(
        return_value=httpx.Response(200, text=_build_xml(prices, resolution="PT15M"))
    )

    result = await fetch_day_ahead(date(2025, 3, 30), region="FI", token="t")

    assert len(result["rows"]) == 92
    assert all(r["interval_minutes"] == 15 for r in result["rows"])
