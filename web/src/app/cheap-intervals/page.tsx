import { getCheapIntervals, PulseApiError } from "@/lib/api";
import { loadDomainConfig } from "@/lib/domain";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";
import { ErrorPanel } from "@/components/ErrorPanel";

export const dynamic = "force-dynamic";

export default async function CheapIntervalsPage({
  searchParams,
}: {
  searchParams: Promise<{ region?: string; date?: string; limit?: string }>;
}) {
  const cfg = loadDomainConfig();
  const params = await searchParams;
  const region = (params.region ?? cfg.default_region).toUpperCase();
  const date = params.date ?? "today";
  const limit = params.limit ? Number(params.limit) : 10;

  let body;
  try {
    const data = await getCheapIntervals(region, date, limit);
    body = (
      <>
        <p className="mb-4 text-sm text-slate-600">
          Region <strong>{data.region}</strong> · {data.date} · cadence{" "}
          {data.interval_minutes ? `${data.interval_minutes}-min` : "n/a"} · top{" "}
          {data.intervals.length}
        </p>
        <div className="overflow-auto rounded border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Start (UTC)</th>
                <th className="px-3 py-2 text-left">End (UTC)</th>
                <th className="px-3 py-2 text-right">spot c/kWh</th>
                <th className="px-3 py-2 text-right">total c/kWh</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.intervals.map((iv) => (
                <tr key={iv.interval_start}>
                  <td className="px-3 py-2">{iv.rank}</td>
                  <td className="px-3 py-2 font-mono">{formatHourMinuteUtc(iv.interval_start)}</td>
                  <td className="px-3 py-2 font-mono">{formatHourMinuteUtc(iv.interval_end)}</td>
                  <td className="px-3 py-2 text-right">{formatPrice(iv.spot_c_kwh)}</td>
                  <td className="px-3 py-2 text-right font-medium">
                    {formatPrice(iv.total_c_kwh)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    );
  } catch (e) {
    const detail = e instanceof PulseApiError ? `${e.message}` : String(e);
    body = <ErrorPanel title="Could not load cheap intervals" detail={detail} />;
  }

  return (
    <section>
      <h1 className="text-2xl font-bold">Cheap intervals</h1>
      <p className="mt-1 text-slate-600">
        Cheapest slots ranked ascending by total c/kWh — useful for scheduling
        appliances.
      </p>
      <div className="mt-6">{body}</div>
    </section>
  );
}
