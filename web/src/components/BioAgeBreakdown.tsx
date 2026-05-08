import { useId, useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { COLOR_TOKENS } from "../lib/stateColors";
import type { BioAge } from "../types";

interface BioAgeBreakdownProps {
  bioAge: BioAge;
}

/* ---------------------------------------------------------------- *
 * BioAgeBreakdown                                                   *
 *                                                                   *
 * Full-width row that renders the proxy as a transparent sum of     *
 * weighted contributors. Two structural choices behind the layout:  *
 *                                                                   *
 *   1) A single big number on the left, annotated with chrono and  *
 *      gap, gives the eye a clear anchor before it asks "why".     *
 *   2) The breakdown on the right uses a horizontal bar per        *
 *      contributor, scaled by `weightPct` (share of total |pull|), *
 *      and labeled with the signed years pulled. The bars sum back *
 *      visually to the headline gap — that's the whole point of    *
 *      this card: prove the number isn't a black box.              *
 *                                                                   *
 * No italics, per design. Visual differentiation comes from font   *
 * weight (Newsreader 300 / 400) and tabular numerals.              *
 * ---------------------------------------------------------------- */

export function BioAgeBreakdown({ bioAge }: BioAgeBreakdownProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanderId = useId();

  const gap = bioAge.years - bioAge.chronologicalYears;
  const gapSigned = `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}`;
  const gapColor =
    gap <= -2 ? "green" : gap <= 0.5 ? "blue" : gap <= 2 ? "amber" : "red";
  const gapTokens = COLOR_TOKENS[gapColor];

  return (
    <section className="mx-auto max-w-6xl px-8">
      <div className="group relative overflow-hidden rounded-md border border-paper-divider bg-paper p-7 shadow-card transition-shadow hover:shadow-card-hover">
        {/* Header — same hairline rule as every other card */}
        <div className="flex items-baseline justify-between border-b border-paper-divider pb-3">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
              Bio-age proxy
            </span>
            <span className="font-mono tabular text-[10px] text-ink-faint">
              transparent sum
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            aria-expanded={isExpanded}
            aria-controls={expanderId}
            aria-label={
              isExpanded ? "Collapse bio-age detail" : "Explain bio-age"
            }
            className="inline-flex h-5 w-5 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-paper-tinted hover:text-ink"
          >
            <span aria-hidden className="text-[14px] leading-none">
              {isExpanded ? "−" : "ⓘ"}
            </span>
          </button>
        </div>

        {/* Headline + breakdown grid */}
        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-10">
          {/* Left: anchor number */}
          <div className="lg:col-span-4">
            <div className="flex items-baseline gap-3">
              <span className="display tabular text-hero font-light leading-none text-ink">
                {bioAge.years.toFixed(1)}
              </span>
              <span className="display text-2xl font-light text-ink-subtle">
                yrs
              </span>
            </div>
            <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-subtle">
                vs chronological
              </span>
              <span className="font-mono tabular text-[11px] font-medium text-ink">
                {bioAge.chronologicalYears}.0 yrs
              </span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span aria-hidden className={`h-1 w-1 rounded-full ${gapTokens.dot}`} />
              <span
                className={`font-mono tabular text-[11px] font-medium ${gapTokens.ink}`}
              >
                {gapSigned}y gap
              </span>
            </div>
            <p className="display mt-4 text-sm font-light leading-relaxed text-ink-muted">
              {bioAge.meaning}
            </p>
          </div>

          {/* Right: contributor bars */}
          <div className="lg:col-span-8">
            <div className="mb-3 flex items-baseline justify-between">
              <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
                What's pulling the gap
              </span>
              <span className="font-mono tabular text-[10px] text-ink-faint">
                {bioAge.breakdown
                  ? bioAge.breakdown.reduce(
                      (s, c) => s + c.pullYears,
                      0,
                    ).toFixed(1)
                  : "—"}{" "}
                y total
              </span>
            </div>
            <ul className="space-y-3">
              {bioAge.breakdown?.map((c) => {
                const tokens = COLOR_TOKENS[c.state];
                const pullSigned = `${c.pullYears >= 0 ? "+" : ""}${c.pullYears.toFixed(1)}`;
                return (
                  <li key={c.name}>
                    {/* Top row: name + signed years pulled */}
                    <div className="flex items-baseline justify-between">
                      <span className="display text-base font-light text-ink">
                        {c.name}
                      </span>
                      <span
                        className={`font-mono tabular text-[12px] font-medium ${tokens.ink}`}
                      >
                        {pullSigned}y
                      </span>
                    </div>
                    {/* Bar — width is share of total |pull| magnitude */}
                    <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-paper-divider">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.max(4, Math.min(100, c.weightPct))}%`,
                          backgroundColor: tokens.spark,
                        }}
                      />
                    </div>
                    {/* Detail line — the user's specific values */}
                    <div className="mt-1 font-mono text-[10px] text-ink-faint">
                      {c.detail}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>

        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              id={expanderId}
              key="bioage-expander"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{
                duration: 0.22,
                ease: [0.32, 0.72, 0, 1],
              }}
              className="overflow-hidden"
            >
              <div className="mt-6 space-y-5 border-t border-paper-divider pt-5">
                {bioAge.reasoning && (
                  <ExpanderSection title="Why this matters for you">
                    <p className="display text-[15px] font-light leading-relaxed text-ink">
                      {bioAge.reasoning}
                    </p>
                  </ExpanderSection>
                )}
                <ExpanderSection title="How it's computed">
                  <p className="text-sm leading-relaxed text-ink-muted">
                    Each contributor produces a signed year-pull = (signal
                    z-score vs an age-cohort baseline) × the
                    spec-weighted coefficient for that signal. The bars
                    above are scaled by each contributor's share of total
                    absolute pull, so length = relative leverage, label =
                    signed years. The headline 24.1 = 21.0 (chrono) + sum
                    of pulls (3.1).
                  </p>
                </ExpanderSection>
                <ExpanderSection title="Known limitations">
                  <p className="text-sm leading-relaxed text-ink-muted">
                    The proxy is illustrative, not medical. Cohort baselines
                    are population-derived; an athlete&apos;s HRV or RHR
                    distribution may shift the &ldquo;normal&rdquo; for a given
                    chronological age and isn&apos;t yet personalized.
                    Genetics, medications, and acute illness windows aren&apos;t
                    captured.
                  </p>
                </ExpanderSection>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
                  skill bio-age-spec §1
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

function ExpanderSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
        {title}
      </div>
      {children}
    </div>
  );
}
