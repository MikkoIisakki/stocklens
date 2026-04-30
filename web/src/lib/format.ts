/**
 * Render an ISO8601 UTC timestamp as a short HH:mm display in UTC.
 * Avoids tz drift between server and client; the page header shows
 * which timezone the values are in.
 */
export function formatHourMinuteUtc(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

export function formatPrice(c_kwh: number): string {
  return c_kwh.toFixed(2);
}
