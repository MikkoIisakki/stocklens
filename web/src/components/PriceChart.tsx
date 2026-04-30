"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";

interface Point {
  interval_start: string;
  total_c_kwh: number;
}

export function PriceChart({ data }: { data: Point[] }) {
  const series = data.map((p) => ({
    label: formatHourMinuteUtc(p.interval_start),
    "c/kWh": p.total_c_kwh,
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={32} fontSize={11} />
          <YAxis fontSize={11} tickFormatter={(v: number) => formatPrice(v)} />
          <Tooltip
            formatter={(value: number) => `${formatPrice(value)} c/kWh`}
            labelFormatter={(label: string) => `UTC ${label}`}
          />
          <Line
            type="monotone"
            dataKey="c/kWh"
            stroke="rgb(var(--brand-primary))"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
