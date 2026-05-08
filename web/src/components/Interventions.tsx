import { MetricPrimer } from "./MetricPrimer";
import type { Intervention } from "../types";

interface InterventionsProps {
  interventions: Intervention[];
}

const IMPACT_TOKENS = {
  HIGH: { label: "HIGH", className: "text-state-red-ink bg-state-red-soft" },
  MED: { label: "MED", className: "text-state-amber-ink bg-state-amber-soft" },
  LOW: { label: "LOW", className: "text-ink-muted bg-paper-tinted" },
} as const;

export function Interventions({ interventions }: InterventionsProps) {
  return (
    <section className="mx-auto max-w-6xl px-8 pb-12">
      <div className="mb-4 flex items-end justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
          Top interventions
        </h2>
        <div className="flex gap-8 text-[10px] font-semibold uppercase tracking-widest text-ink-subtle">
          <span>effort</span>
          <span>impact</span>
        </div>
      </div>

      <ol className="space-y-3">
        {interventions.map((iv, idx) => (
          <li
            key={iv.action}
            className="rounded-xl border border-paper-divider bg-paper p-5"
          >
            <div className="flex items-start gap-4">
              <span className="tabular text-base font-semibold text-ink-subtle">
                {idx + 1}.
              </span>
              <div className="flex-1">
                <div className="flex items-start justify-between gap-4">
                  <div className="text-sm font-medium text-ink">
                    {iv.action}
                  </div>
                  <div className="flex shrink-0 items-center gap-6">
                    <EffortDots level={iv.effort} />
                    <ImpactBadge impact={iv.impact} />
                  </div>
                </div>

                <div className="mt-3">
                  <MetricPrimer
                    variant="inline"
                    label={`Why "${iv.action}" works`}
                    meaning="why this works"
                    mechanism={iv.why}
                    skillRef={iv.skillRef}
                  />
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function EffortDots({ level }: { level: number }) {
  const filled = Math.max(0, Math.min(5, level));
  return (
    <div className="flex items-center gap-1" aria-label={`Effort ${filled} of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${
            i <= filled ? "bg-ink-muted" : "bg-paper-divider"
          }`}
        />
      ))}
    </div>
  );
}

function ImpactBadge({ impact }: { impact: keyof typeof IMPACT_TOKENS }) {
  const tokens = IMPACT_TOKENS[impact];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${tokens.className}`}
    >
      <span aria-hidden>▲</span>
      {tokens.label}
    </span>
  );
}
