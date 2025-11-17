"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import DatePicker from "@/components/form/date-picker";
import Label from "@/components/form/Label";
import Select from "@/components/form/Select";
import Button from "@/components/ui/button/Button";
import Badge from "@/components/ui/badge/Badge";
import { ArrowUpIcon, ArrowDownIcon, ChevronDownIcon } from "@/icons";

const ReactApexChart = dynamic(() => import("react-apexcharts"), { ssr: false });

const BE = "/api/backend";

/* =============================
   Types
============================= */
type StrategyInfo = {
  key: string;
  doc?: string;
  params_schema?: Record<string, unknown>;
  presets?: Record<string, unknown> | null;
};
type Trade = {
  entry_ts: number; exit_ts: number;
  entry_px: number; exit_px: number;
  pnl: number;
};
type BacktestResp = {
  equity: { ts: number; equity: number }[];
  trades: Trade[];
  metrics: Record<string, number>;
};

type TimeMode = "lookback" | "range";

/* =============================
   Helpers
============================= */
function lsKey(strategy: string) { return `presets:${strategy}`; }
function loadUserPresets(strategy: string): Record<string, unknown> {
  try { return JSON.parse(localStorage.getItem(lsKey(strategy)) || "{}"); } catch { return {}; }
}
function saveUserPreset(strategy: string, name: string, params: Record<string, unknown>) {
  const cur = loadUserPresets(strategy); cur[name] = params; localStorage.setItem(lsKey(strategy), JSON.stringify(cur));
}
function deleteUserPreset(strategy: string, name: string) {
  const cur = loadUserPresets(strategy); if (cur[name]) { delete cur[name]; localStorage.setItem(lsKey(strategy), JSON.stringify(cur)); }
}
function defaultsFromSchema(schema: Record<string, unknown> | undefined): Record<string, unknown> {
  const out: Record<string, unknown> = {}; if (!schema?.properties) return out;
  for (const [k, v] of Object.entries(schema.properties as Record<string, { default?: unknown }>)) if ((v as { default?: unknown })?.default !== undefined) out[k] = (v as { default: unknown }).default;
  return out;
}

// Granularity to seconds mapping (matches OANDA API and paper trading)
const GSEC: Record<string, number> = {
  // Seconds
  S5: 5,
  S10: 10,
  S15: 15,
  S30: 30,
  // Minutes
  M1: 60,
  M2: 120,
  M5: 300,
  M15: 900,
  M30: 1800,
  // Hours
  H1: 3600,
  H2: 7200,
  H4: 14400,
  // Daily
  D: 86400,
};
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

// UTC input helpers
function toLocalInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  const y = d.getUTCFullYear();
  const m = pad(d.getUTCMonth() + 1);
  const day = pad(d.getUTCDate());
  const hh = pad(d.getUTCHours());
  const mm = pad(d.getUTCMinutes());
  return `${y}-${m}-${day}T${hh}:${mm}`;
}
function fromLocalInput(s: string) {
  if (!s) return null;
  const [date, time] = s.split("T");
  if (!date || !time) return null;
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  return new Date(Date.UTC(y, (m || 1) - 1, d || 1, hh || 0, mm || 0, 0));
}
function toZ(d: Date | null) { return d ? d.toISOString().replace(/\.\d{3}Z$/, "Z") : null; }

/* =============================
   Page
============================= */
export default function BacktestingPage() {
  // ---------- state ----------
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [strategy, setStrategy] = useState<string>("");

  const [instrument, setInstrument] = useState("EUR_USD");
  const [granularity, setGranularity] = useState<keyof typeof GSEC>("M15");

  // time selection mode
  const [mode, setMode] = useState<TimeMode>("lookback");
  const [lookbackBars, setLookbackBars] = useState<number>(1000);
  const [startLocal, setStartLocal] = useState<string>("");
  const [durationBars, setDurationBars] = useState<number>(1000);

  // results
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [equity, setEquity] = useState<{ ts: number; equity: number }[]>([]);
  const [metrics, setMetrics] = useState<Record<string, number> | null>(null);
  const [derived, setDerived] = useState<Record<string, number> | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  // presets
  const [userPresets, setUserPresets] = useState<Record<string, unknown>>({});
  const [presetSelect, setPresetSelect] = useState<string>("(none)");

  // UI
  const [activeTab, setActiveTab] = useState<"results" | "trades" | "json">("results");
  const [showAllMetrics, setShowAllMetrics] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 12;

  const instruments = ["EUR_USD", "USD_CAD", "GBP_USD", "USD_JPY", "AUD_USD"];

  // defaults
  useEffect(() => {
    const now = new Date();
    setStartLocal(toLocalInput(new Date(now.getTime() - 30 * 24 * 3600 * 1000)));
  }, []);

  // fetch strategies
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BE}/backtest/strategies`, { cache: "no-store" });
        const j = await r.json();
        setStrategies(j.strategies || []);
        if (j.strategies?.length > 0) setStrategy(j.strategies[0].key);
      } catch {
        setErrorText("Failed to load strategies.");
      }
    })();
  }, []);

  const stratInfo = useMemo(() => strategies.find(s => s.key === strategy), [strategies, strategy]);
  const currentSchema = stratInfo?.params_schema;

  // on strategy change
  useEffect(() => {
    if (!strategy) return;
    setUserPresets(loadUserPresets(strategy));
    const sp = stratInfo?.presets?.[instrument] as Record<string, unknown> | undefined;
    if (sp) { setParams(sp); setPresetSelect(`server:${instrument}`); }
    else { const d = defaultsFromSchema(currentSchema); if (Object.keys(d).length) setParams(d); setPresetSelect("(none)"); }
    clearResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategy, stratInfo?.key]);

  // instrument change
  useEffect(() => {
    const sp = stratInfo?.presets?.[instrument] as Record<string, unknown> | undefined;
    if (sp) { setParams(sp); setPresetSelect(`server:${instrument}`); }
    else if (presetSelect.startsWith("server:")) setPresetSelect("(none)");
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instrument]);


  function clearResults() {
    setEquity([]); setMetrics(null); setDerived(null); setTrades([]); setPage(1); setErrorText(null);
  }

  // ---- derived metrics ----
  function computeDerived(
    eq: { ts: number; equity: number }[],
    tradesIn: Trade[],
    initialFromServer?: number | null
  ): Record<string, number> {
    if (!eq?.length) return {};
  
    const start = eq[0].equity;
    const end = eq[eq.length - 1].equity;
  
    const startMs = eq[0].ts * 1000;
    const endMs = eq[eq.length - 1].ts * 1000;
    const days = Math.max(1, (endMs - startMs) / (1000 * 60 * 60 * 24));
    const years = days / 365;
  
    const firstNonZero = eq.find(p => p.equity > 0)?.equity ?? null;
    const base =
      (initialFromServer && initialFromServer > 0) ? initialFromServer :
      (firstNonZero && firstNonZero > 0 ? firstNonZero : null);
  
    // Max drawdown (abs)
    let runningPeak = eq[0].equity;
    let maxDropAbs = 0;
    for (const p of eq) {
      runningPeak = Math.max(runningPeak, p.equity);
      maxDropAbs = Math.min(maxDropAbs, p.equity - runningPeak);
    }
  
    // Trade-derived
    const wins = tradesIn.filter(t => t.pnl > 0);
    const losses = tradesIn.filter(t => t.pnl <= 0);
    const grossProfit = wins.reduce((a, b) => a + b.pnl, 0);
    const grossLoss = -losses.reduce((a, b) => a + b.pnl, 0);
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);
    const winRate = tradesIn.length ? wins.length / tradesIn.length : 0;
    const avgTrade = tradesIn.length ? (grossProfit - grossLoss) / tradesIn.length : 0;

    const avgHold =
      tradesIn.length
        ? tradesIn.reduce((a, t) => a + (t.exit_ts - t.entry_ts), 0) / tradesIn.length / 60
        : 0;
  
    const out: Record<string, number> = {
      "Start Equity": start,
      "End Equity": end,
      "Net PnL": end - start,
      "Max DD (abs)": maxDropAbs,
      "Period (days)": days,
      "Total Trades": tradesIn.length,
      "Win Rate": winRate,
      "Profit Factor": isFinite(profitFactor) ? profitFactor : 0,
      "Avg Trade PnL": avgTrade,
      "Avg Hold (min)": avgHold,
    };

    if (base && base > 0) {
      const totalReturn = end / base - 1;
      let peak = eq[0].equity;
      let maxDDPct = 0;
      for (const p of eq) {
        peak = Math.max(peak, p.equity);
        if (peak > 0) maxDDPct = Math.min(maxDDPct, p.equity / peak - 1);
      }
      const cagr = days >= 1 ? Math.pow(end / base, 1 / years) - 1 : (end / base - 1) * (365 / days);
  
      out["Total Return"] = isFinite(totalReturn) ? totalReturn : 0;
      out["Max Drawdown"] = isFinite(maxDDPct) ? maxDDPct : 0;
      out["CAGR"] = isFinite(cagr) ? cagr : 0;
    }
    return out;
  }  

  // ---- run backtest ----
  async function runBacktest(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setErrorText(null);
    clearResults();

    const payload: Record<string, unknown> = { instrument, granularity, strategy, params, initial_equity: 10000 };

    if (mode === "lookback") {
      payload.count = clamp(lookbackBars, 10, 5000);
    } else {
      const stDate = fromLocalInput(startLocal);
      const drBars = clamp(Math.floor(durationBars || 0), 10, 5000);
      if (!stDate) {
        setErrorText("Please select a valid start date");
        setLoading(false);
        return;
      }
      const rgStart = stDate;
      const rgEndCandidate = new Date(rgStart.getTime() + drBars * gStep * 1000);
      const now = new Date();
      const rgEnd = rgEndCandidate > now ? now : rgEndCandidate;
      
      const sISO = toZ(rgStart);
      const eISO = toZ(rgEnd);
      if (!sISO || !eISO) {
        setErrorText("Invalid date range");
        setLoading(false);
        return;
      }
      payload.start = sISO;
      payload.end = eISO;
    }

    try {
      const r = await fetch(`${BE}/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || "Backtest failed");
      }
      
      const j: BacktestResp = await r.json();

      const eq = j.equity || [];
      setEquity(eq);

      const m = j.metrics || null;
      setMetrics(m);
      
      const initialFromServer = m?.initial_equity ?? null;
      
      const tr = j.trades || [];
      setTrades(tr);
      setDerived(computeDerived(eq, tr, initialFromServer));

      setActiveTab("results");
      toast("Backtest complete!", "ok");
    } catch (err: unknown) {
      setErrorText((err as Error).message || "Backtest error");
      toast((err as Error).message || "Backtest error", "error");
    } finally {
      setLoading(false);
    }
  }

  // ---- formatting ----
  function formatMetric(label: string, value: number): string {
    if (!Number.isFinite(value)) return String(value);
  
    // percent styles
    if (/(rate|win|loss|return|drawdown(?!\s*\(abs\))|roi|cagr)/i.test(label)) {
      const pct = Math.abs(value) <= 5 ? value * 100 : value;
      return `${pct.toFixed(2)}%`;
    }
    // integers
    if (/(^|\s)(trades?|count|num|samples?|bars?|period)/i.test(label)) {
      return Math.round(value).toString();
    }
    // money-like
    if (/(pnl|equity|balance|max\s*dd\s*\(abs\))/i.test(label)) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    // ratios
    if (/(sharpe|sortino|factor)/i.test(label)) {
      return value.toFixed(2);
    }
    // durations
    if (/hold/i.test(label)) {
      return `${value.toFixed(1)}`;
    }
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  
  // Key stats (top display)
  const keyStatOrder = [
    "Total Return",
    "Max Drawdown",
    "Profit Factor",
    "Win Rate",
    "CAGR",
    "Total Trades",
  ];

  const merged = useMemo(() => {
    const d = derived ? Object.entries(derived) as [string, number][] : [];
    const m = metrics ? Object.entries(metrics) as [string, number][] : [];
    const set = new Map<string, number>();
    
    d.forEach(([k, v]) => set.set(k, v));
    
    const skipBackendKeys = new Set([
      'total_return', 'max_drawdown', 'max_drawdown_pct', 
      'initial_equity', 'final_equity', 'num_trades', 'win_rate'
    ]);
    
    m.forEach(([k, v]) => { 
      if (!set.has(k) && !skipBackendKeys.has(k)) {
        set.set(k, v);
      }
    });
    
    return Array.from(set.entries());
  }, [derived, metrics]);

  const keyStats = keyStatOrder
    .map(k => merged.find(([kk]) => kk.toLowerCase() === k.toLowerCase()))
    .filter(Boolean) as [string, number][];

  const allMetrics = merged;

  // Equity chart
  const equitySeries = useMemo(
    () => [{ name: "Equity", data: equity.map(p => ({ x: p.ts * 1000, y: p.equity })) }],
    [equity]
  );

  // pagination
  const totalPages = Math.max(1, Math.ceil(trades.length / pageSize));
  const pageRows = trades.slice((page - 1) * pageSize, page * pageSize);

  function exportCSV() {
    if (!trades.length) return toast("No trades to export");
    const header = "entry_ts,exit_ts,entry_px,exit_px,pnl\n";
    const rows = trades.map(t => [t.entry_ts, t.exit_ts, t.entry_px, t.exit_px, t.pnl].join(",")).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a");
    a.href = url; a.download = `${strategy}_${instrument}_${granularity}_trades.csv`; a.click(); URL.revokeObjectURL(url);
  }

  const gStep = GSEC[granularity] ?? 60;
  const overLimit = (mode === "lookback" ? lookbackBars : durationBars) > 5000;
  const hasValidRange = mode === "lookback" ? lookbackBars >= 10 : !!startLocal && durationBars >= 10;
  const canRun = !loading && !overLimit && hasValidRange;

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
          <div>
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">Backtesting</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Historical simulation against OANDA data
          </p>
          </div>
        {strategy && (
          <Badge color="success">
            {strategy}
          </Badge>
        )}
      </header>

      {/* Controls Form */}
      <form onSubmit={runBacktest} className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm space-y-5">
        {/* Row 1: Instrument, Granularity, Strategy */}
        <div className="grid gap-6 md:grid-cols-3">
          <div>
            <Label>Forex Pair</Label>
            <div className="relative">
              <Select
                options={instruments.map(i => ({ value: i, label: i }))}
                defaultValue={instrument}
                onChange={(v) => { setInstrument(v); setPage(1); }}
                className="dark:bg-gray-900"
              />
              <span className="absolute text-gray-500 -translate-y-1/2 pointer-events-none right-3 top-1/2 dark:text-gray-400">
                <ChevronDownIcon />
          </span>
        </div>
          </div>

          <div>
            <Label>Timeframe</Label>
            <div className="relative">
              <select
                value={granularity}
                onChange={(e) => setGranularity(e.target.value as keyof typeof GSEC)}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 py-3 px-4 pr-10 text-gray-800 dark:text-white/90 outline-none transition focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 dark:focus:border-brand-800 appearance-none"
              >
                <optgroup label="Seconds">
                  <option value="S5">5 Seconds</option>
                  <option value="S10">10 Seconds</option>
                  <option value="S15">15 Seconds</option>
                  <option value="S30">30 Seconds</option>
                </optgroup>
                <optgroup label="Minutes">
                  <option value="M1">1 Minute</option>
                  <option value="M2">2 Minutes</option>
                  <option value="M5">5 Minutes</option>
                  <option value="M15">15 Minutes</option>
                  <option value="M30">30 Minutes</option>
                </optgroup>
                <optgroup label="Hours">
                  <option value="H1">1 Hour</option>
                  <option value="H2">2 Hours</option>
                  <option value="H4">4 Hours</option>
                </optgroup>
                <optgroup label="Daily">
                  <option value="D">Daily</option>
                </optgroup>
              </select>
              <span className="absolute text-gray-500 -translate-y-1/2 pointer-events-none right-3 top-1/2 dark:text-gray-400">
                <ChevronDownIcon />
              </span>
            </div>
          </div>

          <div>
            <Label>Strategy</Label>
            <div className="relative">
              <Select
                options={strategies.map(s => ({ value: s.key, label: s.key }))}
                defaultValue={strategy}
                onChange={(v) => { setStrategy(v); setParams({}); setPresetSelect("(none)"); }}
                className="dark:bg-gray-900"
              />
              <span className="absolute text-gray-500 -translate-y-1/2 pointer-events-none right-3 top-1/2 dark:text-gray-400">
                <ChevronDownIcon />
              </span>
            </div>
          </div>
        </div>

        {/* Row 2: Time Mode */}
        <div>
          <Label>Time Selection Mode</Label>
          <div className="flex items-center gap-6 mt-2">
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="timeMode"
                checked={mode === "lookback"}
                onChange={() => setMode("lookback")}
                className="w-4 h-4 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">Lookback</span>
              </label>
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="timeMode"
                checked={mode === "range"}
                onChange={() => setMode("range")}
                className="w-4 h-4 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">Date Range</span>
              </label>
            </div>
            </div>

        {/* Row 3: Time Controls */}
        {mode === "lookback" ? (
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label htmlFor="barsSlider">Lookback Bars</Label>
              <input
                type="number"
                min={10}
                max={5000}
                step={10}
                value={lookbackBars}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  if (!isNaN(v)) setLookbackBars(clamp(v, 10, 5000));
                }}
                className="w-20 px-2 py-1 text-sm text-right border rounded-lg dark:bg-gray-800 dark:border-gray-700 dark:text-white/90 border-gray-300"
              />
            </div>
            <input
              id="barsSlider"
              type="range"
              min={10}
              max={5000}
              step={10}
              value={lookbackBars}
              onChange={(e) => setLookbackBars(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-brand-600"
            />
            {overLimit && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">Maximum 5000 bars</p>
            )}
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            <DatePicker
              id="start-date-range"
              mode="single"
              label="Start Date (UTC)"
              placeholder="Select start date"
              onChange={(dates) => {
                if (dates && dates.length > 0) {
                  const selectedDate = new Date(dates[0]);
                  setStartLocal(toLocalInput(selectedDate));
                }
              }}
            />
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label htmlFor="durationSlider">Duration (bars)</Label>
                <input
                  type="number"
                  min={10}
                  max={5000}
                  step={10}
                  value={durationBars}
                  onChange={(e) => {
                    const v = parseInt(e.target.value);
                    if (!isNaN(v)) setDurationBars(clamp(v, 10, 5000));
                  }}
                  className="w-20 px-2 py-1 text-sm text-right border rounded-lg dark:bg-gray-800 dark:border-gray-700 dark:text-white/90 border-gray-300"
                />
              </div>
              <input
                id="durationSlider"
                type="range"
                min={10}
                max={5000}
                step={10}
                value={durationBars}
                onChange={(e) => setDurationBars(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-brand-600"
              />
              {overLimit && (
                <p className="mt-1 text-xs text-red-600 dark:text-red-400">Maximum 5000 bars</p>
              )}
            </div>
          </div>
        )}

        {/* Row 4: Preset Selection */}
        <div className="grid gap-6 md:grid-cols-3">
          <div>
            <Label>Load Preset</Label>
            <div className="relative">
              <Select
                options={[
                  { value: "(none)", label: "(none)" },
                  ...(stratInfo?.presets ? Object.keys(stratInfo.presets).map(k => ({ value: `server:${k}`, label: `📊 ${k}` })) : []),
                  ...(Object.keys(userPresets).map(k => ({ value: `user:${k}`, label: `👤 ${k}` }))),
                ]}
                defaultValue={presetSelect}
                onChange={setPresetSelect}
                className="dark:bg-gray-900"
              />
              <span className="absolute text-gray-500 -translate-y-1/2 pointer-events-none right-3 top-1/2 dark:text-gray-400">
                <ChevronDownIcon />
              </span>
            </div>
          </div>
          <div className="flex items-end gap-2">
            <button
              type="button"
              onClick={() => {
                if (presetSelect === "(none)") return;
                const [src, name] = presetSelect.split(":");
                if (src === "server") { const p = stratInfo?.presets?.[name] as Record<string, unknown> | undefined; if (p) setParams(p); }
                else { const p = userPresets?.[name] as Record<string, unknown> | undefined; if (p) setParams(p); }
                toast("Preset applied!");
              }}
              disabled={presetSelect === "(none)"}
              className={`w-full px-5 py-2.5 text-sm font-medium rounded-lg transition inline-flex items-center justify-center gap-2 ${
                presetSelect !== "(none)"
                  ? "bg-brand-500 text-white hover:bg-brand-600"
                  : "bg-brand-300 text-white cursor-not-allowed opacity-50"
              }`}
            >
              Apply Preset
            </button>
            <button
              type="button"
              onClick={() => {
                const name = prompt("Enter preset name:")?.trim();
                if (!name) return;
                saveUserPreset(strategy, name, params);
                setUserPresets(loadUserPresets(strategy));
                setPresetSelect(`user:${name}`);
                toast("Preset saved!");
              }}
              className="w-full px-5 py-2.5 text-sm font-medium rounded-lg transition bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/[0.03] dark:hover:text-gray-300"
            >
              Save As...
            </button>
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={() => {
                if (!presetSelect.startsWith("user:")) return;
                const name = presetSelect.split(":")[1];
                if (confirm(`Delete preset "${name}"?`)) {
                  deleteUserPreset(strategy, name);
                  setUserPresets(loadUserPresets(strategy));
                  setPresetSelect("(none)");
                  toast("Preset deleted");
                }
              }}
              disabled={!presetSelect.startsWith("user:")}
              className={`w-full px-5 py-2.5 text-sm font-medium rounded-lg transition ${
                presetSelect.startsWith("user:")
                  ? "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/[0.03] dark:hover:text-gray-300"
                  : "cursor-not-allowed opacity-50 bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-600"
              }`}
            >
              Delete Preset
            </button>
          </div>
        </div>

        {/* Strategy Parameters */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 bg-gray-50/50 dark:bg-gray-800/20">
          <h4 className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            {stratInfo?.doc || "Strategy Parameters"}
          </h4>
            {currentSchema?.properties ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(currentSchema.properties as Record<string, { type?: string; default?: unknown; multipleOf?: number; minimum?: number; maximum?: number }>).map(([k, v]) => {
                const type = v.type;
                const isNum = type === "number" || type === "integer";
                const isBool = type === "boolean";
                const rawVal = params[k];
                const fallback = v.default;
                const resolvedVal = rawVal !== undefined ? rawVal : fallback;
                const fieldVal = typeof resolvedVal === "string" || typeof resolvedVal === "number" ? String(resolvedVal) : "";
                const boolVal = (() => {
                  if (typeof resolvedVal === "boolean") return resolvedVal;
                  if (typeof resolvedVal === "string") {
                    const lower = resolvedVal.toLowerCase();
                    if (lower === "true") return true;
                    if (lower === "false") return false;
                  }
                  return Boolean(resolvedVal);
                })();
                const step = v.multipleOf || (type === "integer" ? 1 : "any");
                return (
                  <div key={k}>
                    <Label htmlFor={`param-${k}`}>{k}</Label>
                    {isBool ? (
                      <label className="flex items-center gap-3">
                        <input
                          id={`param-${k}`}
                          type="checkbox"
                          checked={boolVal}
                          onChange={(e) =>
                            setParams(p => ({ ...p, [k]: e.target.checked }))
                          }
                          className="h-5 w-5 rounded border-gray-300 text-brand-600 focus:ring-brand-500 dark:bg-gray-900 dark:border-gray-700"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">{boolVal ? "True" : "False"}</span>
                      </label>
                    ) : (
                      <input
                        id={`param-${k}`}
                        type={isNum ? "number" : "text"}
                        step={isNum ? step : undefined}
                        min={isNum ? String(v.minimum) : undefined}
                        max={isNum ? String(v.maximum) : undefined}
                        value={fieldVal}
                        onChange={(e) =>
                          setParams(p => ({ ...p, [k]: isNum ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value }))
                        }
                        className="h-11 w-full rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2.5 text-sm dark:bg-gray-900 dark:text-white/90 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:focus:border-brand-800"
                      />
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div>
              <Label htmlFor="params-json">Parameters (JSON)</Label>
                <textarea
                id="params-json"
                className="w-full min-h-[100px] p-3 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-800 dark:text-white/90"
                  value={JSON.stringify(params, null, 2)}
                  onChange={(e) => { try { setParams(JSON.parse(e.target.value) as Record<string, unknown>); } catch {} }}
                />
            </div>
            )}
          </div>

        {/* Submit */}
        <div className="flex justify-end pt-1">
          <button
            type="submit"
            disabled={!canRun}
            className={`px-6 py-2.5 text-sm font-medium rounded-lg transition inline-flex items-center justify-center gap-2 ${
              canRun
                ? "bg-brand-500 text-white hover:bg-brand-600"
                : "bg-brand-300 text-white cursor-not-allowed opacity-50"
            }`}
          >
            {loading ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </form>

      {/* Results Section */}
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden shadow-sm">
        {/* Tabs */}
        <div className="flex gap-1 p-1 border-b border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20">
          <Tab active={activeTab === "results"} onClick={() => setActiveTab("results")}>
            Results
          </Tab>
          <Tab active={activeTab === "trades"} onClick={() => setActiveTab("trades")}>
            Trades ({trades.length})
          </Tab>
          <Tab active={activeTab === "json"} onClick={() => setActiveTab("json")}>
            Raw JSON
          </Tab>
        </div>

        <div className="p-6">
          {errorText && (
            <div className="mb-6 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {errorText}
            </div>
          )}

          {loading && (
            <div className="grid gap-4">
              <Skeleton className="h-64" />
              <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
                {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24" />)}
              </div>
            </div>
          )}

          {!loading && activeTab === "results" && (
            <div className="space-y-6">
              {/* Equity Chart */}
              {equity.length > 0 ? (
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-4">
                  <h3 className="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">
                    Equity Curve
                  </h3>
                  <EquityAreaChart series={equitySeries} />
                </div>
              ) : (
                <Empty
                  title="No results yet"
                  subtitle="Configure your backtest parameters and click 'Run Backtest' to see results."
                />
              )}

              {/* Key Stats Cards */}
              {keyStats.length > 0 && (
                <div>
                  <h3 className="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">
                    Key Performance Metrics
                  </h3>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {keyStats.map(([label, value]) => {
                      const formatted = formatMetric(label, value);
                      const isPositive = value > 0;
                      const isPercent = /(rate|return|drawdown|cagr)/i.test(label);
                      const showBadge = isPercent && value !== 0 && !/win\s*rate/i.test(label);

                      return (
                        <StatCard
                          key={label}
                          label={label}
                          value={formatted}
                          trend={showBadge ? (isPositive ? "up" : "down") : undefined}
                          trendValue={showBadge ? formatted : undefined}
                        />
                      );
                    })}
              </div>
                </div>
              )}

              {/* All Metrics - Collapsible */}
              {allMetrics.length > 0 && (
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-5">
                  <button
                    onClick={() => setShowAllMetrics(!showAllMetrics)}
                    className="flex items-center justify-between w-full text-left"
                  >
                    <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                      All Metrics ({allMetrics.length})
                    </h3>
                    <span className={`transform transition-transform ${showAllMetrics ? "rotate-180" : ""}`}>
                      <ChevronDownIcon className="text-gray-500 dark:text-gray-400" />
                    </span>
                  </button>

                  {showAllMetrics && (
                    <div className="grid gap-3 mt-4 md:grid-cols-4">
                      {allMetrics.map(([label, value]) => (
                        <div
                          key={label}
                          className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50/50 dark:bg-gray-800/20"
                        >
                          <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
                          <div className="mt-1 text-base font-semibold text-gray-800 dark:text-white/90">
                            {formatMetric(label, value)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {!loading && activeTab === "trades" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {trades.length ? `${trades.length} trades` : "No trades"}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </Button>
                  <span className="flex items-center px-3 text-sm text-gray-600 dark:text-gray-400">
                    Page {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                  >
                    Next
                  </Button>
                  <Button onClick={exportCSV} disabled={!trades.length}>
                    Export CSV
                  </Button>
                </div>
              </div>

              {trades.length > 0 ? (
                <div className="overflow-x-auto border border-gray-200 dark:border-gray-800 rounded-xl">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20">
                        <Th>Entry Time</Th>
                        <Th>Exit Time</Th>
                        <Th numeric>Entry Price</Th>
                        <Th numeric>Exit Price</Th>
                        <Th numeric>PnL</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((t, i) => (
                        <tr key={i} className="border-b border-gray-200 dark:border-gray-800">
                          <Td>{new Date(t.entry_ts * 1000).toLocaleString()}</Td>
                          <Td>{new Date(t.exit_ts * 1000).toLocaleString()}</Td>
                          <Td numeric>{t.entry_px.toFixed(5)}</Td>
                          <Td numeric>{t.exit_px.toFixed(5)}</Td>
                          <Td
                            numeric
                            className={
                              t.pnl >= 0
                                ? "!text-green-600 !dark:text-green-300 font-medium"
                                : "!text-red-600 !dark:text-red-300 font-medium"
                            }
                          >
                            {t.pnl.toFixed(2)}
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                ) : (
                <Empty
                  title="No trades"
                  subtitle="This strategy didn't generate any trades with the current parameters."
                />
                )}
            </div>
          )}

          {!loading && activeTab === "json" && (
            <pre className="p-4 overflow-auto text-xs border border-gray-200 dark:border-gray-800 rounded-xl bg-gray-50 dark:bg-gray-800/20 text-gray-800 dark:text-gray-200">
              {JSON.stringify(
                {
                  equity: equity.slice(0, 50),
                  metrics,
                  derived,
                  trades: trades.slice(0, 50),
                },
                null,
                2
              )}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

/* =============================
   Components
============================= */
function StatCard({
  label,
  value,
  trend,
  trendValue,
}: {
  label: string;
  value: string;
  trend?: "up" | "down";
  trendValue?: string;
}) {
  return (
    <div className="p-5 border border-gray-200 rounded-2xl bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex items-end justify-between">
        <div>
          <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
          <h4 className="mt-2 text-2xl font-bold text-gray-800 dark:text-white/90">
            {value}
          </h4>
        </div>
        {trend && trendValue && (
          <Badge color={trend === "up" ? "success" : "error"}>
            {trend === "up" ? <ArrowUpIcon /> : <ArrowDownIcon />}
            {trendValue}
          </Badge>
        )}
      </div>
    </div>
  );
}

function EquityAreaChart({ series }: { series: { name: string; data: { x: number; y: number }[] }[] }) {
  const isDark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");
  
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const options: any = {
    legend: { show: false },
    colors: ["#465FFF"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      height: 310,
      type: "area",
      toolbar: { show: false },
      background: "transparent",
    },
    stroke: {
      curve: "straight",
      width: 2,
    },
    fill: {
      type: "gradient",
      gradient: {
        opacityFrom: 0.55,
        opacityTo: 0,
      },
    },
    markers: {
      size: 0,
      strokeColors: "#fff",
      strokeWidth: 2,
      hover: { size: 6 },
    },
    grid: {
      borderColor: isDark ? "#374151" : "#e5e7eb",
      strokeDashArray: 3,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
    },
    dataLabels: { enabled: false },
    tooltip: {
      enabled: true,
      theme: isDark ? "dark" : "light",
      x: { format: "dd MMM HH:mm" },
    },
    xaxis: {
      type: "datetime",
      labels: {
        datetimeUTC: false,
        style: {
          fontSize: "12px",
          colors: isDark ? "#9ca3af" : "#6B7280",
        },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: {
          fontSize: "12px",
          colors: isDark ? "#9ca3af" : "#6B7280",
        },
        formatter: function(val: number) {
          return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
        },
      },
    },
  };
  
  return <ReactApexChart options={options} series={series} type="area" height={310} />;
}

function Tab({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
        active
          ? "bg-white dark:bg-gray-900 text-gray-800 dark:text-white/90 border border-gray-200 dark:border-gray-700"
          : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function Th({ children, numeric }: { children: React.ReactNode; numeric?: boolean }) {
  return (
    <th className={`px-4 py-3 text-xs font-semibold text-gray-700 dark:text-gray-300 ${numeric ? "text-right" : "text-left"}`}>
      {children}
    </th>
  );
}

function Td({
  children,
  numeric,
  className = "",
}: {
  children: React.ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  return (
    <td className={`px-4 py-3 text-gray-800 dark:text-white/90 ${numeric ? "text-right" : "text-left"} ${className}`}>
      {children}
    </td>
  );
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800 ${className}`} />;
}

function Empty({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="text-lg font-medium text-gray-800 dark:text-white/90">{title}</div>
      {subtitle && <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">{subtitle}</div>}
    </div>
  );
}

function toast(msg: string, kind: "ok" | "error" = "ok") {
  if (typeof window === "undefined") return;
  const el = document.createElement("div");
  el.textContent = msg;
  el.className =
    "fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg text-sm shadow-lg font-medium " +
    (kind === "ok"
      ? "bg-success-600 text-white"
      : "bg-error-600 text-white");
  el.style.transition = "all 0.3s ease";
  document.body.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
  }, 2500);
  setTimeout(() => el.remove(), 2800);
}
