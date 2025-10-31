import type { Metadata } from "next";

export const metadata: Metadata = { title: "Paper Trading" };

export default function PaperTradingPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Paper Trading</h1>
      <p className="text-sm text-zinc-500">
        Placeholder page. This will use OANDA Practice pricing in shadow mode first.
      </p>
      <div className="rounded-lg border p-4">
        Coming soon: connect OANDA practice stream, show live PnL, start/stop strategy.
      </div>
    </div>
  );
}
