import { useId, useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { COLOR_TOKENS } from "../lib/stateColors";
import type { DiagnosticQuestion, Divergence, StateColor } from "../types";

interface DivergenceStripProps {
  divergence: Divergence;
  accentColor: StateColor;
}

/* ---------------------------------------------------------------- *
 * DivergenceStrip                                                   *
 *                                                                   *
 * A divergence isn't a state, it's a *story*. The card is split    *
 * into three layers, each visible without clicking ⓘ:               *
 *                                                                   *
 *   1) Headline: pattern + interpretation (the "what")             *
 *   2) Drivers:  the specific signals pulling the composite the    *
 *                wrong way, with their actual values (the "what's  *
 *                going wrong")                                      *
 *   3) Diagnostic question: a multiple-choice prompt the user can  *
 *                click to firm up the scoring layer's confidence.  *
 *                When answered, shows the confirmation locally;    *
 *                in production this would persist back to the      *
 *                user's profile and influence subsequent scores.   *
 *                                                                   *
 * The expander only carries the long-form personal reasoning and   *
 * the generic divergence-matrix explainer — the layers above are   *
 * load-bearing on first read.                                       *
 *                                                                   *
 * No italics anywhere; visual weight comes from font-light vs      *
 * font-medium and from accent-tinted left border.                  *
 * ---------------------------------------------------------------- */

export function DivergenceStrip({
  divergence,
  accentColor,
}: DivergenceStripProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [answeredId, setAnsweredId] = useState<string | null>(null);
  const expanderId = useId();
  const tokens = COLOR_TOKENS[accentColor];

  if (!divergence.triggered) return null;

  return (
    <section className="mx-auto max-w-6xl px-8">
      <div
        className="group relative overflow-hidden rounded-md border border-paper-divider bg-paper p-7 shadow-card"
        style={{
          borderLeftWidth: 3,
          borderLeftColor: tokens.spark,
        }}
      >
        {/* Header */}
        <div className="flex items-baseline justify-between border-b border-paper-divider pb-3">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className={`inline-flex h-1.5 w-1.5 rounded-full ${tokens.dot}`}
            />
            <span
              className={`font-mono text-[10px] font-medium uppercase tracking-[0.22em] ${tokens.ink}`}
            >
              Signal Divergence
            </span>
            {divergence.skillRef && (
              <span className="font-mono text-[10px] text-ink-faint">
                {divergence.skillRef}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            aria-expanded={isExpanded}
            aria-controls={expanderId}
            aria-label={
              isExpanded ? "Collapse divergence detail" : "Explain divergence"
            }
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-paper-tinted hover:text-ink"
          >
            <span aria-hidden className="text-[14px] leading-none">
              {isExpanded ? "−" : "ⓘ"}
            </span>
          </button>
        </div>

        {/* Headline (pattern) — serif, NOT italic */}
        <h3 className="display mt-4 text-2xl font-light leading-snug text-ink">
          {divergence.pattern}
        </h3>
        <p className="display mt-2 text-base font-light leading-relaxed text-ink-muted">
          {divergence.interpretation}
        </p>

        {/* Drivers — what's actually going wrong, visible without ⓘ */}
        {divergence.drivers && divergence.drivers.length > 0 && (
          <div className="mt-6 border-t border-paper-divider pt-5">
            <div className="mb-3 flex items-baseline justify-between">
              <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
                What's driving it
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                {divergence.drivers.length} signals
              </span>
            </div>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {divergence.drivers.map((d) => {
                const dTokens = COLOR_TOKENS[d.state];
                return (
                  <li
                    key={d.signal}
                    className="flex gap-3 rounded-sm border-l-2 pl-3"
                    style={{ borderLeftColor: dTokens.spark }}
                  >
                    <div className="flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-subtle">
                          {d.signal}
                        </span>
                        <span
                          className={`font-mono tabular text-[11px] font-medium ${dTokens.ink}`}
                        >
                          {d.value}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-relaxed text-ink-muted">
                        {d.note}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Diagnostic question — visible without ⓘ. When an option is
            selected, the prompt + buttons swap for a confirmation that
            quotes the option's response payload. Without this payoff the
            question reads as decoration; with it, answering visibly
            teaches the system. */}
        {divergence.question && (
          <DiagnosticBlock
            question={divergence.question}
            answeredId={answeredId}
            onAnswer={setAnsweredId}
            tokens={tokens}
          />
        )}

        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              id={expanderId}
              key="div-expander"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{
                duration: 0.22,
                ease: [0.32, 0.72, 0, 1],
              }}
              className="overflow-hidden"
            >
              <div className="mt-6 space-y-4 border-t border-paper-divider pt-5">
                {divergence.reasoning && (
                  <ExpanderSection title="Why this matters for you">
                    <p className="display text-[15px] font-light leading-relaxed text-ink">
                      {divergence.reasoning}
                    </p>
                  </ExpanderSection>
                )}
                <ExpanderSection title="How to read divergences">
                  <p className="text-sm leading-relaxed text-ink-muted">
                    The divergence matrix in skill §4 records this exact
                    pair: when one lens improves while another stays
                    compromised, the wearable is leading the body. The
                    action implication is to hold reload until the
                    slower-moving signal catches up.
                  </p>
                </ExpanderSection>
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

/* ---------------------------------------------------------------- *
 * DiagnosticBlock                                                   *
 *                                                                   *
 * Two-state widget. Until the user picks an option, it shows the   *
 * prompt + multiple-choice buttons. After the pick, it shows a     *
 * confirmation that quotes the option's response — confidence      *
 * delta, action implications, narrative headline.                   *
 *                                                                   *
 * The "Change answer" affordance returns to the question state.    *
 * In production, the response payload would be computed by the     *
 * scoring layer; here it's pre-baked per option in mock data.     *
 * ---------------------------------------------------------------- */

function DiagnosticBlock({
  question,
  answeredId,
  onAnswer,
  tokens,
}: {
  question: DiagnosticQuestion;
  answeredId: string | null;
  onAnswer: (id: string | null) => void;
  tokens: (typeof COLOR_TOKENS)[StateColor];
}) {
  const selected = answeredId
    ? question.options.find((o) => o.id === answeredId)
    : undefined;

  if (selected) {
    const r = selected.response;
    return (
      <div
        className={`mt-6 rounded-sm border px-5 py-4 ${tokens.border} ${tokens.tint}`}
      >
        <div className="flex items-baseline justify-between gap-3">
          <span
            className={`font-mono text-[10px] font-semibold uppercase tracking-[0.22em] ${tokens.ink}`}
          >
            Answer logged
          </span>
          <button
            type="button"
            onClick={() => onAnswer(null)}
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint underline-offset-2 transition-colors hover:text-ink hover:underline"
          >
            Change answer
          </button>
        </div>
        {/* Headline confirmation — display body, full ink */}
        <p className="display mt-2 text-base font-light leading-relaxed text-ink">
          {r.headline}
        </p>
        {r.confidenceTransition && (
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-subtle">
              Composite confidence
            </span>
            <span
              className={`font-mono tabular text-[11px] font-medium ${tokens.ink}`}
            >
              {r.confidenceTransition}
            </span>
          </div>
        )}
        {/* Action implications — bullets */}
        {r.actions.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {r.actions.map((a, i) => (
              <li
                key={i}
                className="flex gap-2 text-sm leading-relaxed text-ink-muted"
              >
                <span aria-hidden className="font-mono text-ink-faint">
                  →
                </span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  // Unanswered — show prompt + buttons
  return (
    <div className="mt-6 rounded-sm border border-paper-divider bg-paper-tinted/50 px-5 py-4">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
          We need to ask
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">
          improves confidence
        </span>
      </div>
      <p className="display mt-2 text-base font-light leading-relaxed text-ink">
        {question.prompt}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {question.options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => onAnswer(opt.id)}
            className="display rounded-sm border border-paper-divider bg-paper px-3 py-1.5 text-sm font-light text-ink-muted transition-colors hover:border-ink-faint hover:text-ink"
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
