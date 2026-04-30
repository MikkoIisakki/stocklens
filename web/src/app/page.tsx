import { getPrices, PulseApiError } from "@/lib/api";
import { loadDomainConfig } from "@/lib/domain";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";
import { PriceChart } from "@/components/PriceChart";
import { ErrorPanel } from "@/components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function PricesPage({
  searchParams,
}: {
  searchParams: Promise<{ region?: string; date?: string }>;
}) {
  const cfg = loadDomainConfig();
  const params = await searchParams;
  const region = (params.region ?? cfg.default_region).toUpperCase();
  const date = params.date ?? "today";

  let body;
  try {
    const data = await getPrices(region, date);
    body = (
      <>
        <p className="mb-4 text-sm text-slate-600">
          Region <strong>{data.region}</strong> · {data.date} · cadence{" "}
          {data.interval_minutes ? `${data.interval_minutes}-min` : "n/a"} · {data.prices.length}{" "}
          intervals
        </p>
        <PriceChart data={data.prices} />
        <h2 className="mt-8 text-lg font-semibold">Raw intervals</h2>
        <div className="mt-2 overflow-auto rounded border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Start (UTC)</th>
                <th className="px-3 py-2 text-right">spot c/kWh</th>
                <th className="px-3 py-2 text-right">total c/kWh</th>
                <th className="px-3 py-2 text-right">EUR/MWh</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.prices.map((p) => (
                <tr key={p.interval_start}>
                  <td className="px-3 py-2 font-mono">{formatHourMinuteUtc(p.interval_start)}</td>
                  <td className="px-3 py-2 text-right">{formatPrice(p.spot_c_kwh)}</td>
                  <td className="px-3 py-2 text-right font-medium">
                    {formatPrice(p.total_c_kwh)}
                  </td>
                  <td className="px-3 py-2 text-right">{p.price_eur_mwh.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    );
  } catch (e) {
    const detail = e instanceof PulseApiError ? `${e.message}` : String(e);
    body = <ErrorPanel title="Could not load prices" detail={detail} />;
  }

  return (
    <section>
      <h1 className="text-2xl font-bold">Prices</h1>
      <p className="mt-1 text-slate-600">{cfg.description}</p>
      <div className="mt-6">{body}</div>
    </section>
  );
}
