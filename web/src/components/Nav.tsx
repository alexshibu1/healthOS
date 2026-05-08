import type { DataStream } from "../types";

interface NavProps {
  date?: string;
  streams: DataStream[];
}

const STATUS_DOT: Record<DataStream["status"], string> = {
  fresh: "bg-state-green",
  stale: "bg-state-amber",
  old: "bg-state-red",
  missing: "bg-ink-faint",
};

export function Nav({ date, streams }: NavProps) {
  const today =
    date ??
    new Date().toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });

  return (
    <header className="sticky top-0 z-40 border-b border-paper-divider bg-paper-tinted/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-baseline justify-between px-8 py-4">
        {/* Wordmark — editorial serif lockup */}
        <div className="flex items-baseline gap-3">
          <span className="display text-lg font-medium tracking-tight text-ink">
            health
            <span className="display font-light text-ink-muted">OS</span>
          </span>
        </div>

        {/* Date + dateline */}
        <span className="font-mono tabular text-[11px] uppercase tracking-[0.18em] text-ink-muted">
          {today}
        </span>
      </div>

      {/* Stream status ribbon — small dotted labels, no pills */}
      <div className="border-t border-paper-divider bg-paper-tinted/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-1.5 px-8 py-2">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
            Sources
          </span>
          {streams.map((s) => (
            <span
              key={s.source}
              className="inline-flex items-baseline gap-1.5"
              title={`${s.label} · last sync ${s.synced} ago`}
            >
              <span
                aria-hidden
                className={`relative inline-block h-1.5 w-1.5 rounded-full ${STATUS_DOT[s.status]}`}
              />
              <span className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-muted">
                {s.label}
              </span>
              <span className="font-mono tabular text-[10px] text-ink-faint">
                {s.synced}
              </span>
            </span>
          ))}
        </div>
      </div>
    </header>
  );
}
