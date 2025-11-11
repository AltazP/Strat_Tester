export default function MetricGrid({
    title,
    items,
    format,
  }: {
    title: string;
    items: [string, number][];
    format?: (label: string, value: number) => string;
  }) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-3">{title}</h3>
        <div className="grid gap-3 md:grid-cols-4">
          {items.map(([k,v]) => (
            <div key={k} className="rounded-xl border border-zinc-200 dark:border-gray-800 p-3 bg-white/60 dark:bg-gray-900/40">
              <div className="text-xs text-zinc-500 dark:text-zinc-400">{k}</div>
              <div className="text-lg font-semibold">{format ? format(k, v) : String(v)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  