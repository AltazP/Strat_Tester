import type { Metadata } from "next";

export const metadata: Metadata = { title: "Live Trading" };

export default function LiveTradingPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Live Trading</h1>
      <p className="text-sm text-zinc-500">
        Placeholder page. This will remain disabled until an ENABLE_TRADING guard is on.
      </p>
      <div className="rounded-lg border p-4">
        Coming soon: risk caps, circuit breaker, and order audit trail.
      </div>
    </div>
  );
}
