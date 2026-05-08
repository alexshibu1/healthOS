import { useId, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { COLOR_TOKENS } from "../lib/stateColors";
import type { Divergence, StateColor } from "../types";

interface DivergenceStripProps {
  divergence: Divergence;
  accentColor: StateColor;
}

const EXPAND_TRANSITION = {
  duration: 0.22,
  ease: [0.32, 0.72, 0, 1] as [number, number, number, number],
};

export function DivergenceStrip({
  divergence,
  accentColor,
}: DivergenceStripProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanderId = useId();
  const tokens = COLOR_TOKENS[accentColor];

  if (!divergence.triggered) return null;

  return (
    <section className="mx-auto max-w-6xl px-8 pb-6">
      <div
        className={`group relative rounded-lg border-l-2 ${tokens.border} ${tokens.tint} px-5 py-4`}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-semibold uppercase tracking-widest ${tokens.ink}`}
              >
                Signal divergence
              </span>
              {divergence.skillRef && (
                <span className="font-mono text-xs text-ink-subtle">
                  {divergence.skillRef}
                </span>
              )}
            </div>
            <div className="mt-1.5 text-sm font-medium text-ink">
              {divergence.pattern}
            </div>
            <div className="mt-0.5 text-sm text-ink-muted">
              {divergence.interpretation}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            aria-expanded={isExpanded}
            aria-controls={expanderId}
            aria-label={
              isExpanded ? "Collapse divergence detail" : "Explain divergence"
            }
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-ink-subtle transition-colors hover:bg-paper hover:text-ink"
          >
            <span aria-hidden className="text-[14px] leading-none">
              {isExpanded ? "−" : "ⓘ"}
            </span>
          </button>
        </div>

        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              id={expanderId}
              key="div-expander"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={EXPAND_TRANSITION}
              className="overflow-hidden"
            >
              <div className="mt-4 border-t border-paper-divider pt-4 text-sm leading-relaxed text-ink-muted">
                The divergence matrix in skill §4 records this exact pair:
                when one lens improves while another stays compromised, the
                wearable is leading the body. The action implication is to
                hold reload until the slower-moving signal (in this case,
                the inflammatory marker) catches up. The score has already
                been downweighted by the post-illness confidence multiplier
                — the divergence is the explanation for why.
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
