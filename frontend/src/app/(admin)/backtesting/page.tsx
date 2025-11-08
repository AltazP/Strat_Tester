"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const LineChartOne = dynamic(() => import("@/components/charts/line/LineChartOne"), { ssr: false });

const BE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

type StrategyInfo = {
  key: string;
  doc?: string;
  params_schema?: any;
};

export default function BacktestingPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [strategy, setStrategy] = useState<string>("");
  const [params, setParams] = useState<Record<string, any>>({});
  const [instrument, setInstrument] = useState("EUR_USD");
  const [granularity, setGranularity] = useState("M5");
  const [slider, setSlider] = useState(5);
  const [series, setSeries] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const instruments = ["EUR_USD", "USD_CAD", "GBP_USD", "USD_JPY", "AUD_USD"];
  const granularities = ["S5", "M1", "M5", "M15", "H1", "D"];

  const candleCount = (g: string, s: number) => {
    const base: Record<string, number> = { S5:100, M1:200, M5:300, M15:400, H1:500, D:200 };
    return (base[g] || 200) * (s + 1);
  };

  const count = candleCount(granularity, slider);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BE}/backtest/strategies`);
        const j = await r.json();
        setStrategies(j.strategies);
        if (j.strategies.length > 0) setStrategy(j.strategies[0].key);
      } catch (err) {
        console.error(err);
      }
    })();
  }, []);

  // Render dynamic form inputs from schema
  const currentSchema = strategies.find(s => s.key === strategy)?.params_schema;

  function renderSchemaFields(schema: any) {
    if (!schema || !schema.properties) return null;
    return Object.entries(schema.properties).map(([k, v]: any) => {
      const type = v.type;
      const fieldVal = params[k] ?? v.default ?? "";

      return (
        <label key={k} className="text-sm grid gap-1">
          <span className="text-zinc-500">{k}</span>
          {type === "number" ? (
            <input
              type="number"
              className="border rounded px-2 py-1 bg-transparent"
              value={fieldVal}
              onChange={(e) => setParams((p) => ({ ...p, [k]: parseFloat(e.target.value) }))}
            />
          ) : (
            <input
              className="border rounded px-2 py-1 bg-transparent"
              value={fieldVal}
              onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
            />
          )}
        </label>
      );
    });
  }

  async function runBacktest(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setSeries([]);
    setMetrics(null);
    setTrades([]);

    try {
      const r = await fetch(`${BE}/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instrument,
          granularity,
          count,
          strategy,
          params,
        }),
      });

      const j = await r.json();
      if (!r.ok) throw new Error(j?.error || "Backtest failed");

      setSeries([{
        name: "Equity",
        data: j.equity.map((p: any) => ({ x: p.ts * 1000, y: p.equity }))
      }]);
      setMetrics(j.metrics);
      setTrades(j.trades);
    } catch (err: any) {
      alert(err?.message);
    }
    setLoading(false);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Backtesting</h1>

      {/* Controls */}
      <form onSubmit={runBacktest} className="rounded-lg border p-4 grid gap-4 md:grid-cols-4">

        {/* Pair */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Pair</span>
          <select className="border rounded px-2 py-1 bg-transparent"
            value={instrument}
            onChange={(e) => setInstrument(e.target.value)}>
            {instruments.map(s => <option key={s}>{s}</option>)}
          </select>
        </label>

        {/* Timeframe */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Granularity</span>
          <select className="border rounded px-2 py-1 bg-transparent"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}>
            {granularities.map(s => <option key={s}>{s}</option>)}
          </select>
        </label>

        {/* Lookback */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Lookback (0-20)</span>
          <input type="range" min={0} max={20} value={slider}
            onChange={(e) => setSlider(parseInt(e.target.value))} />
          <span className="text-xs text-zinc-500">Candles: {count}</span>
        </label>

        {/* Strategy */}
        <label className="text-sm grid gap-1">
          <span className="text-zinc-500">Strategy</span>
          <select className="border rounded px-2 py-1 bg-transparent"
            value={strategy}
            onChange={(e) => { setStrategy(e.target.value); setParams({}); }}>
            {strategies.map(s => <option key={s.key} value={s.key}>{s.key}</option>)}
          </select>
        </label>

        {/* Dynamic params OR JSON fallback */}
        <div className="md:col-span-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {currentSchema?.properties
            ? renderSchemaFields(currentSchema)
            : (
              <label className="text-sm grid gap-1 md:col-span-2">
                <span className="text-zinc-500">Params (JSON)</span>
                <textarea
                  className="border rounded px-2 py-1 bg-transparent min-h-[96px]"
                  value={JSON.stringify(params, null, 2)}
                  onChange={(e) => {
                    try { setParams(JSON.parse(e.target.value)); } catch {}
                  }}
                />
              </label>
            )
          }
        </div>

        <div className="flex items-end">
          <button type="submit"
            className="px-3 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
            disabled={loading}>
            {loading ? "Running…" : "Run"}
          </button>
        </div>
      </form>

      {/* Chart */}
      <div className="rounded-lg border p-4">
        {series.length > 0
          ? <LineChartOne series={series} title="Equity Curve" />
          : <p className="text-sm text-zinc-500">Run a backtest to see results.</p>}
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="rounded-lg border p-4">
          <h2 className="font-medium mb-2">Metrics</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(metrics).map(([k, v]) => (
              <div key={k} className="rounded border p-3">
                <div className="text-xs text-zinc-500">{k}</div>
                <div className="text-lg font-semibold">{Number(v).toFixed(4)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trades */}
      <div className="rounded-lg border p-4">
        <h2 className="font-medium mb-2">Trades</h2>
        {trades.length === 0
          ? <p className="text-sm text-zinc-500">No trades.</p>
          : (
            <div className="overflow-x-auto">
              <table className="min-w-[600px] text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th>Entry</th><th>Exit</th>
                    <th>Entry Px</th><th>Exit Px</th><th>PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t, i) => (
                    <tr key={i} className="border-b">
                      <td>{new Date(t.entry_ts * 1000).toLocaleString()}</td>
                      <td>{new Date(t.exit_ts * 1000).toLocaleString()}</td>
                      <td>{t.entry_px.toFixed(5)}</td>
                      <td>{t.exit_px.toFixed(5)}</td>
                      <td className={t.pnl>=0?"text-green-600":"text-red-600"}>
                        {t.pnl.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </div>
    </div>
  );
}