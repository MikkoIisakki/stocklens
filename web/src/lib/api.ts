import "server-only";

/**
 * Server-side API client for the Pulse backend.
 *
 * Holds the bearer token in a process env var (`PULSE_API_KEY`) so it
 * never reaches the browser. Pages call these helpers from server
 * components / route handlers; the response is rendered server-side.
 */

export interface IntervalPrice {
  interval_start: string;
  interval_end: string;
  interval_minutes: number;
  price_eur_mwh: number;
  spot_c_kwh: number;
  total_c_kwh: number;
}

export interface PricesResponse {
  region: string;
  date: string;
  interval_minutes: number | null;
  prices: IntervalPrice[];
}

export interface RankedInterval extends IntervalPrice {
  rank: number;
}

export interface CheapIntervalsResponse {
  region: string;
  date: string;
  interval_minutes: number | null;
  intervals: RankedInterval[];
}

export interface Alert {
  id: number;
  price_date: string;
  peak_c_kwh: number;
  peak_interval_start: string;
  threshold_c_kwh: number;
  fired_at: string;
}

export interface AlertsResponse {
  region: string;
  alerts: Alert[];
}

export class PulseApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly url: string,
  ) {
    super(message);
    this.name = "PulseApiError";
  }
}

function baseUrl(): string {
  const url = process.env.PULSE_API_BASE_URL;
  if (!url) {
    throw new Error("PULSE_API_BASE_URL is not set");
  }
  return url.replace(/\/+$/, "");
}

function authHeader(): Record<string, string> {
  const key = process.env.PULSE_API_KEY;
  if (!key) {
    throw new Error("PULSE_API_KEY is not set");
  }
  return { Authorization: `Bearer ${key}` };
}

async function fetchJson<T>(path: string): Promise<T> {
  const url = `${baseUrl()}${path}`;
  const res = await fetch(url, {
    headers: { ...authHeader(), Accept: "application/json" },
    // Server components are RSC; opt out of caching to keep data fresh.
    cache: "no-store",
  });
  if (!res.ok) {
    throw new PulseApiError(
      `Pulse API ${res.status} for ${path}`,
      res.status,
      url,
    );
  }
  return (await res.json()) as T;
}

export function getPrices(region: string, date: string): Promise<PricesResponse> {
  const qs = new URLSearchParams({ region, date }).toString();
  return fetchJson<PricesResponse>(`/v1/energy/prices?${qs}`);
}

export function getCheapIntervals(
  region: string,
  date: string,
  limit = 10,
): Promise<CheapIntervalsResponse> {
  const qs = new URLSearchParams({
    region,
    date,
    limit: String(limit),
  }).toString();
  return fetchJson<CheapIntervalsResponse>(`/v1/energy/cheap-intervals?${qs}`);
}

export function getAlerts(region: string): Promise<AlertsResponse> {
  const qs = new URLSearchParams({ region }).toString();
  return fetchJson<AlertsResponse>(`/v1/energy/alerts?${qs}`);
}
