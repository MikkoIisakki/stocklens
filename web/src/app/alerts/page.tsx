import { getAlerts, PulseApiError } from "@/lib/api";
import { loadDomainConfig } from "@/lib/domain";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";
import { ErrorPanel } from "@/components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ region?: string }>;
}) {
  const cfg = loadDomainConfig();
  const params = await searchParams;
  const region = (params.region ?? cfg.default_region).toUpperCase();

  let body;
  try {
    const data = await getAlerts(region);
    body = data.alerts.length === 0 ? (
      <p className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
        No alerts have fired for {data.region} yet.
      </p>
    ) : (
      <div className="overflow-auto rounded border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2 text-left">Peak slot (UTC)</th>
              <th className="px-3 py-2 text-right">peak c/kWh</th>
              <th className="px-3 py-2 text-right">threshold</th>
              <th className="px-3 py-2 text-left">Fired at</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {data.alerts.map((a) => (
              <tr key={a.id}>
                <td className="px-3 py-2 font-mono">{a.price_date}</td>
                <td className="px-3 py-2 font-mono">{formatHourMinuteUtc(a.peak_interval_start)}</td>
                <td className="px-3 py-2 text-right font-medium">{formatPrice(a.peak_c_kwh)}</td>
                <td className="px-3 py-2 text-right">{formatPrice(a.threshold_c_kwh)}</td>
                <td className="px-3 py-2 font-mono text-xs">{a.fired_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  } catch (e) {
    const detail = e instanceof PulseApiError ? `${e.message}` : String(e);
    body = <ErrorPanel title="Could not load alerts" detail={detail} />;
  }

  return (
    <section>
      <h1 className="text-2xl font-bold">Alerts</h1>
      <p className="mt-1 text-slate-600">
        Threshold alerts that have fired for the current region, newest first.
      </p>
      <div className="mt-6">{body}</div>
    </section>
  );
}
