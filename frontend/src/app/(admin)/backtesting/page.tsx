"use client";

import { useMemo, useState } from "react";
import LineChartOne, { LineSeries } from "@/components/charts/line/LineChartOne";

type Granularity = "S5" | "M1" | "M5" | "M15" | "H1" | "D";
const INSTRUMENTS = ["EUR_USD", "USD_CAD", "GBP_USD", "USD_JPY", "AUD_USD"] as const;
const GRANULARITIES: Granularity[] = ["S5", "M1", "M5", "M15", "H1", "D"];

// map slider (0..20) to candle count; feel free to change curve
function sliderToCount(v: number, g: Granularity) {
  // denser for lower timeframes
  const base = { S5: 100 * (v + 1), M1: 200 * (v + 1), M5: 300 * (v + 1), M15: 400 * (v + 1), H1: 500 * (v + 1), D: 200 * (v + 1) } as const;
  return base[g];
}

export default function BacktestingPage() {
  const [instrument, setInstrument] = useState<(typeof INSTRUMENTS)[number]>("EUR_USD");
  const [granularity, setGranularity] = useState<Granularity>("M5");
  const [slider, setSlider] = useState<number>(5); // 0..20
  const [loading, setLoading] = useState(false);
  const [series, setSeries] = useState<LineSeries[]>([]);

  const count = useMemo(() => sliderToCount(slider, granularity), [slider, granularity]);

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const qs = new URLSearchParams({
        instrument,
        granularity,
        count: String(count),
        price: "M", // mid prices
      }).toString();

      const res = await fetch(`/api/oanda/candles?${qs}`, { cache: "no-store" });
      const data = await res.json();

      if (!res.ok) throw new Error(data?.error || "Fetch failed");

      // OANDA payload: {candles: [{time, complete, volume, mid: {o,h,l,c}}], instrument, granularity}
      const pts = (data.candles || [])
        .filter((c: any) => c.complete && c.mid?.c)
        .map((c: any) => ({ x: new Date(c.time).getTime(), y: Number(c.mid.c) }));

      setSeries([{ name: `${instrument} (${granularity})`, data: pts }]);
    } catch (err: any) {
      alert(err?.message || "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Backtesting</h1>

      {/* Controls */}
      <form onSubmit={onRun} className="rounded-lg border p-4 grid gap-4 md:grid-cols-4">
        {/* Instrument */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Currency Pair</span>
          <select
            className="border rounded px-2 py-1 bg-transparent"
            value={instrument}
            onChange={(e) => setInstrument(e.target.value as any)}
          >
            {INSTRUMENTS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>

        {/* Granularity */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Granularity</span>
          <select
            className="border rounded px-2 py-1 bg-transparent"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value as Granularity)}
          >
            {GRANULARITIES.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </label>

        {/* Lookback slider */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Lookback (0–20)</span>
          <input
            type="range"
            min={0}
            max={20}
            value={slider}
            onChange={(e) => setSlider(Number(e.target.value))}
          />
          <span className="text-xs text-zinc-500">Candles: {count}</span>
        </label>

        {/* Submit */}
        <div className="flex items-end">
          <button
            type="submit"
            className="px-3 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
            disabled={loading}
          >
            {loading ? "Loading…" : "Run"}
          </button>
        </div>
      </form>

      {/* Chart */}
      <div className="rounded-lg border p-4">
        {series.length === 0 ? (
          <p className="text-sm text-zinc-500">Run the query to see the chart.</p>
        ) : (
          <LineChartOne series={series} title="Close Price" />
        )}
      </div>

      {/* (Optional) extras to add later:
          - Checkbox “Include volume”
          - Radio M/O/H/L (mid vs bid/ask)
          - Date range pickers (use 'from'/'to' instead of 'count')
          - Multiple instruments overlay */}
    </div>
  );
}
