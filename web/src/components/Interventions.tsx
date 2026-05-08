import type {
  Intervention,
  InterventionCategory,
  InterventionProjection,
} from "../types";

interface InterventionsProps {
  interventions: Intervention[];
}

/* ---------------------------------------------------------------- *
 * Interventions ("The Three Levers")                                *
 *                                                                   *
 * This is the punchline of the whole report. Three changes the     *
 * user should make this month, with the reasoning visible without  *
 * any interaction. Architectural choices:                          *
 *                                                                   *
 *   1) Why is visible by default. The old version hid it behind   *
 *      a click — wrong call for the most important section.       *
 *   2) Impact gets a large color-saturated chip top-right, like    *
 *      a magazine cover stamp. It's the second thing the eye lands *
 *      on after the action heading. HIGH impact reads as a moral  *
 *      claim; LOW reads as bookkeeping.                            *
 *   3) Effort renders as 5 bars (filled / unfilled) so the user   *
 *      can compare relative cost across the three at a glance.    *
 *   4) Action heading is display serif, light, larger than any    *
 *      action elsewhere on the page. The Three Levers should      *
 *      out-typeset everything else.                                *
 *   5) No italics. Visual contrast comes from weight and tracking. *
 * ---------------------------------------------------------------- */

const IMPACT_TOKENS = {
  HIGH: {
    label: "HIGH IMPACT",
    chipText: "text-state-red-ink",
    chipBorder: "border-state-red",
    chipBg: "bg-state-red-tint",
    dot: "bg-state-red",
  },
  MED: {
    label: "MED IMPACT",
    chipText: "text-state-amber-ink",
    chipBorder: "border-state-amber",
    chipBg: "bg-state-amber-tint",
    dot: "bg-state-amber",
  },
  LOW: {
    label: "LOW IMPACT",
    chipText: "text-ink-muted",
    chipBorder: "border-paper-divider",
    chipBg: "bg-paper-tinted",
    dot: "bg-ink-faint",
  },
} as const;

const CATEGORY_LABEL: Record<InterventionCategory, string> = {
  sleep: "Sleep",
  training: "Training",
  recovery: "Recovery",
  nutrition: "Nutrition",
};

const CATEGORY_DOT: Record<InterventionCategory, string> = {
  sleep: "bg-state-purple",
  training: "bg-state-red",
  recovery: "bg-state-blue",
  nutrition: "bg-state-green",
};

export function Interventions({ interventions }: InterventionsProps) {
  return (
    <section className="mx-auto max-w-6xl px-8">
      <ol className="space-y-5">
        {interventions.map((iv, idx) => {
          const impactTokens = IMPACT_TOKENS[iv.impact];
          return (
            <li
              key={iv.action}
              className="group relative overflow-hidden rounded-md border border-paper-divider bg-paper p-8 shadow-card transition-shadow hover:shadow-card-hover"
            >
              {/* Header: ordinal + category on the left, impact chip on the right */}
              <div className="flex items-start justify-between gap-4 border-b border-paper-divider pb-4">
                <div className="flex items-baseline gap-4">
                  <span className="display tabular text-3xl font-light leading-none text-ink-faint">
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <span className="inline-flex items-center gap-1.5 pb-0.5">
                    <span
                      aria-hidden
                      className={`h-1.5 w-1.5 rounded-full ${CATEGORY_DOT[iv.category]}`}
                    />
                    <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
                      {CATEGORY_LABEL[iv.category]}
                    </span>
                  </span>
                </div>
                <ImpactChip
                  tokens={impactTokens}
                  projectedComposite={iv.projectedComposite}
                  projectedBioAge={iv.projectedBioAge}
                />
              </div>

              {/* Action heading — the largest heading on the page */}
              <h3 className="display mt-5 text-3xl font-light leading-tight text-ink">
                {iv.action}
              </h3>

              {/* Why prose — visible by default, body, generous leading */}
              <p className="display mt-4 max-w-3xl text-base font-light leading-relaxed text-ink-muted">
                {iv.why}
              </p>

              {/* Footer — effort bars, skill ref, shortcut */}
              <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-paper-divider pt-4">
                <EffortReadout level={iv.effort} />
                <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
                  skill {iv.skillRef}
                </span>
                {iv.shortcut && (
                  <kbd className="ml-auto hidden rounded border border-paper-divider bg-paper-tinted px-2 py-0.5 font-mono text-[10px] font-medium text-ink-muted md:inline-flex">
                    {iv.shortcut}
                  </kbd>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/* ---------------------------------------------------------------- *
 * ImpactChip — the multi-line "magazine stamp"                      *
 *                                                                   *
 * Bigger structural job than before: it now carries quantities,    *
 * not just a label. The architecture:                              *
 *                                                                   *
 *   ┌──────────────────────┐                                       *
 *   │ ● HIGH IMPACT        │  ← verdict (mono semibold)             *
 *   │ ──────────────       │  ← hairline rule                       *
 *   │ +6 pts on April      │  ← projected composite                 *
 *   │ −1.4y bio-age gap    │  ← projected bio-age                   *
 *   └──────────────────────┘                                       *
 *                                                                   *
 * This makes levers numerically comparable (the +6 lever beats the *
 * +2 lever even when both say HIGH) AND ties them back to the      *
 * bio-age breakdown above — the page's meta-loop.                  *
 *                                                                   *
 * Projection rows are optional: a Z2-cap lever doesn't move the    *
 * bio-age proxy, so it just shows the composite line.              *
 * ---------------------------------------------------------------- */

function ImpactChip({
  tokens,
  projectedComposite,
  projectedBioAge,
}: {
  tokens: (typeof IMPACT_TOKENS)[keyof typeof IMPACT_TOKENS];
  projectedComposite?: InterventionProjection;
  projectedBioAge?: InterventionProjection;
}) {
  const hasProjections = projectedComposite || projectedBioAge;
  return (
    <span
      className={`inline-flex shrink-0 flex-col items-stretch gap-1.5 rounded-sm border px-3 py-2 ${tokens.chipBorder} ${tokens.chipBg}`}
    >
      {/* Verdict row */}
      <span className="inline-flex items-center gap-2">
        <span
          aria-hidden
          className={`h-1.5 w-1.5 rounded-full ${tokens.dot}`}
        />
        <span
          className={`font-mono text-[11px] font-semibold uppercase tracking-[0.22em] ${tokens.chipText}`}
        >
          {tokens.label}
        </span>
      </span>

      {/* Hairline + projections — only when at least one projection exists */}
      {hasProjections && (
        <>
          <span
            aria-hidden
            className={`h-px w-full ${tokens.chipBorder} border-t opacity-50`}
          />
          <span className="flex flex-col gap-0.5">
            {projectedComposite && (
              <ProjectionRow
                projection={projectedComposite}
                tokens={tokens}
                emphasis="primary"
              />
            )}
            {projectedBioAge && (
              <ProjectionRow
                projection={projectedBioAge}
                tokens={tokens}
                emphasis="secondary"
              />
            )}
          </span>
        </>
      )}
    </span>
  );
}

function ProjectionRow({
  projection,
  tokens,
  emphasis,
}: {
  projection: InterventionProjection;
  tokens: (typeof IMPACT_TOKENS)[keyof typeof IMPACT_TOKENS];
  emphasis: "primary" | "secondary";
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span
        className={`font-mono tabular text-[11px] leading-tight ${
          emphasis === "primary" ? "font-medium" : "font-normal"
        } ${tokens.chipText}`}
      >
        {projection.value}
      </span>
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
        {projection.on}
      </span>
    </span>
  );
}

/* ---------------------------------------------------------------- *
 * EffortReadout — 5 bars, filled by level                          *
 *                                                                   *
 * Visual scaling lets the user compare relative cost across the    *
 * three levers at a glance, which a "3/5" string can't do.         *
 * ---------------------------------------------------------------- */

function EffortReadout({ level }: { level: number }) {
  const filled = Math.max(0, Math.min(5, level));
  return (
    <span
      className="inline-flex items-baseline gap-2"
      aria-label={`Effort ${filled} of 5`}
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-subtle">
        Effort
      </span>
      <span className="inline-flex gap-[3px]" aria-hidden>
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className={`h-2.5 w-1 rounded-[1px] ${
              i < filled ? "bg-ink-muted" : "bg-paper-divider"
            }`}
          />
        ))}
      </span>
      <span className="font-mono tabular text-[10px] text-ink-faint">
        {filled}/5
      </span>
    </span>
  );
}
