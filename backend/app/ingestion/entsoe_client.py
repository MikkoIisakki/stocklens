"""Async HTTP client for the ENTSO-E Transparency Platform day-ahead price API.

ENTSO-E publishes spot prices for every EU bidding zone via a RESTful API that
returns XML ``Publication_MarketDocument`` payloads (``documentType=A44`` for
day-ahead prices).

Authentication is by query parameter ``securityToken`` — the token is obtained
by registering at https://transparency.entsoe.eu (Settings → Web API Security
Token).

Resolution:
    Each ``<Period>`` carries a ``<resolution>PTnnM</resolution>`` element. We
    parse that into ``interval_minutes`` (15 for ``PT15M``, 60 for ``PT60M``,
    etc.) and emit one row per ``<Point>`` so callers preserve the resolution
    ENTSO-E publishes. See ADR-005 for the platform convention.

Endpoint: GET https://web-api.tp.entsoe.eu/api
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://web-api.tp.entsoe.eu/api"
_TIMEOUT = 30.0  # seconds
_DOCUMENT_TYPE = "A44"  # Day-ahead prices

# ENTSO-E XML uses default namespaces that change per document version.
# Match by local-name to stay compatible across schema revisions.
_PUBLICATION_LOCAL = "Publication_MarketDocument"
_ACK_LOCAL = "Acknowledgement_MarketDocument"

_RESOLUTION_RE = re.compile(r"^PT(\d+)M$")  # e.g. PT15M, PT60M


# Bidding zone code → ENTSO-E EIC (Energy Identification Code).
# Source: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
# Keep aligned with db/seeds/002_energy_regions.sql.
REGION_TO_EIC: dict[str, str] = {
    "FI": "10YFI-1--------U",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
    "EE": "10Y1001A1001A39I",
    "LT": "10YLT-1001A0008Q",
    "LV": "10YLV-1001A00074",
}


class EntsoeAuthError(RuntimeError):
    """Raised when ENTSO-E returns 401 — token is missing, invalid, or revoked."""


class EntsoeNoDataError(RuntimeError):
    """Raised when ENTSO-E returns an Acknowledgement_MarketDocument (no data for window)."""


def _local(tag: str) -> str:
    """Return the local-name portion of a possibly-namespaced XML tag."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _fetch_sync(target_date: date, region: str, token: str) -> str:
    """Synchronous HTTP GET — runs in a thread executor.

    Returns the raw response text (XML). Raises ``EntsoeAuthError`` on 401.
    """
    eic = REGION_TO_EIC[region]
    period_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    period_end = period_start + timedelta(days=1)
    params = {
        "securityToken": token,
        "documentType": _DOCUMENT_TYPE,
        "in_Domain": eic,
        "out_Domain": eic,
        "periodStart": period_start.strftime("%Y%m%d%H%M"),
        "periodEnd": period_end.strftime("%Y%m%d%H%M"),
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.get(_BASE_URL, params=params)
        if response.status_code == 401:
            raise EntsoeAuthError("ENTSO-E returned 401 Unauthorized — check ENTSOE_API_TOKEN")
        response.raise_for_status()
        return response.text


def _parse_resolution_minutes(text: str | None) -> int:
    """Parse an ENTSO-E ``<resolution>`` value (e.g. ``PT15M``) into minutes.

    Falls back to 60 when missing/unparseable; logs a warning.
    """
    if not text:
        logger.warning("ENTSO-E Period missing resolution element; defaulting to 60 min")
        return 60
    m = _RESOLUTION_RE.match(text.strip())
    if not m:
        logger.warning("Unrecognised ENTSO-E resolution %r; defaulting to 60 min", text)
        return 60
    return int(m.group(1))


def _parse_xml(xml_text: str, target_date: date) -> dict[str, Any]:
    """Parse an ENTSO-E A44 Publication_MarketDocument into interval rows.

    Produces:
        {
            "deliveryDate": "YYYY-MM-DD",
            "currency": "EUR",
            "rows": [
                {
                    "interval_start": datetime UTC,
                    "interval_end":   datetime UTC,
                    "interval_minutes": 15 | 60 | ...,
                    "value": <float EUR/MWh>,
                },
                ...
            ]
        }

    Raises:
        EntsoeNoDataError: if the response is an Acknowledgement_MarketDocument
            (ENTSO-E's way of saying "no matching data found").
    """
    root = ET.fromstring(xml_text)
    root_local = _local(root.tag)

    if root_local == _ACK_LOCAL:
        reason_text = ""
        for elem in root.iter():
            if _local(elem.tag) == "text" and elem.text:
                reason_text = elem.text
                break
        raise EntsoeNoDataError(
            f"ENTSO-E returned no data for {target_date}: {reason_text or 'unknown reason'}"
        )

    if root_local != _PUBLICATION_LOCAL:
        raise RuntimeError(f"Unexpected ENTSO-E root element: {root_local}")

    rows: list[dict[str, Any]] = []
    for series in root.iter():
        if _local(series.tag) != "TimeSeries":
            continue
        for period in series.iter():
            if _local(period.tag) != "Period":
                continue
            period_start = _read_period_start(period, fallback=target_date)
            interval_minutes = _parse_resolution_minutes(_read_text_child(period, "resolution"))
            step = timedelta(minutes=interval_minutes)
            for point in period.iter():
                if _local(point.tag) != "Point":
                    continue
                position = _read_int_child(point, "position")
                price = _read_float_child(point, "price.amount")
                if position is None or price is None:
                    continue
                slot_start = period_start + step * (position - 1)
                slot_end = slot_start + step
                rows.append(
                    {
                        "interval_start": slot_start,
                        "interval_end": slot_end,
                        "interval_minutes": interval_minutes,
                        "value": price,
                    }
                )

    return {
        "deliveryDate": target_date.isoformat(),
        "currency": "EUR",
        "rows": rows,
    }


def _read_period_start(period: ET.Element, fallback: date) -> datetime:
    """Extract the period's UTC start datetime; fall back to midnight UTC of *fallback*."""
    for elem in period.iter():
        if _local(elem.tag) == "start" and elem.text:
            text = elem.text.strip()
            # ENTSO-E uses "2025-01-15T00:00Z" (no seconds). Normalise to ISO with offset.
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)
            except ValueError:
                break
    return datetime.combine(fallback, datetime.min.time(), tzinfo=UTC)


def _read_text_child(parent: ET.Element, local_name: str) -> str | None:
    for child in parent:
        if _local(child.tag) == local_name and child.text:
            return child.text
    return None


def _read_int_child(parent: ET.Element, local_name: str) -> int | None:
    text = _read_text_child(parent, local_name)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _read_float_child(parent: ET.Element, local_name: str) -> float | None:
    text = _read_text_child(parent, local_name)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


async def fetch_day_ahead(target_date: date, region: str = "FI", *, token: str) -> dict[str, Any]:
    """Fetch ENTSO-E day-ahead prices for *region* on *target_date*.

    Args:
        target_date: Delivery date (UTC). Prices are returned for the 24-hour
            window ``[target_date 00:00Z, target_date+1 00:00Z)``.
        region: Bidding zone code (FI, SE3, SE4, EE, LT, LV).
        token: ENTSO-E Web API Security Token.

    Returns:
        Dict with ``rows`` shaped per the interval-based platform convention
        (ADR-005): each row has ``interval_start`` / ``interval_end``
        (UTC datetimes), ``interval_minutes`` (15 or 60), and ``value`` in
        EUR/MWh.

    Raises:
        KeyError: if *region* is not in ``REGION_TO_EIC``.
        EntsoeAuthError: if the API returns HTTP 401.
        EntsoeNoDataError: if the API returns an Acknowledgement document.
        httpx.HTTPStatusError: on other non-2xx responses.
        httpx.TimeoutException: if the request times out.
    """
    loop = asyncio.get_running_loop()
    xml_text = await loop.run_in_executor(None, _fetch_sync, target_date, region, token)
    parsed = _parse_xml(xml_text, target_date)
    rows = parsed["rows"]
    logger.debug(
        "ENTSO-E %s %s: %d points, resolution=%s min",
        region,
        target_date,
        len(rows),
        rows[0]["interval_minutes"] if rows else "n/a",
    )
    return parsed
