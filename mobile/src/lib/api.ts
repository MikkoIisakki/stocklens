import { getApiBaseUrl, getApiKey } from "./domain";

/**
 * Pulse REST API client for the mobile shell.
 *
 * Mirrors web/src/lib/api.ts; differs only in how the env (API URL +
 * key) is sourced — see `./domain.ts`.
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

async function fetchJson<T>(path: string): Promise<T> {
  const apiKey = getApiKey();
  if (!apiKey) {
    throw new Error(
      "EXPO_PUBLIC_API_KEY is empty. Set it before `expo start` or in the EAS build profile.",
    );
  }
  const url = `${getApiBaseUrl()}${path}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    throw new PulseApiError(`Pulse API ${res.status} for ${path}`, res.status, url);
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
  const qs = new URLSearchParams({ region, date, limit: String(limit) }).toString();
  return fetchJson<CheapIntervalsResponse>(`/v1/energy/cheap-intervals?${qs}`);
}

export function getAlerts(region: string): Promise<AlertsResponse> {
  const qs = new URLSearchParams({ region }).toString();
  return fetchJson<AlertsResponse>(`/v1/energy/alerts?${qs}`);
}
