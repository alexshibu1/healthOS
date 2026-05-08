import { COLOR_TOKENS } from "../lib/stateColors";
import type { SecondaryReadout } from "../types";

interface SecondaryReadoutsProps {
  readouts: SecondaryReadout[];
}

/* ---------------------------------------------------------------- *
 * SecondaryReadouts                                                 *
 *                                                                   *
 * A horizontal strip of glance-only derived signals — the things    *
 * a user wants to scan quickly but doesn't need a full card for.    *
 *                                                                   *
 * Each readout is one mono row: dot · label · value · note.        *
 * No expander, no chart. Color = signal severity.                  *
 *                                                                   *
 * The intent is to address "more elements" without crowding the     *
 * main signals. Treat this as the editorial "marginalia" — small   *
 * notes alongside the headline.                                     *
 * ---------------------------------------------------------------- */

export function SecondaryReadouts({ readouts }: SecondaryReadoutsProps) {
  if (!readouts.length) return null;
  return (
    <section className="mx-auto max-w-6xl px-8">
      <div className="rounded-md border border-paper-divider bg-paper-tinted/40 px-6 py-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
            Marginalia
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">
            secondary signals
          </span>
        </div>
        <ul className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          {readouts.map((r) => {
            const tokens = COLOR_TOKENS[r.state];
            return (
              <li key={r.label} className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`h-1 w-1 shrink-0 rounded-full ${tokens.dot}`}
                  />
                  <span className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-subtle">
                    {r.label}
                  </span>
                </div>
                <span
                  className={`display tabular text-xl font-light leading-none ${tokens.ink}`}
                >
                  {r.value}
                </span>
                <span className="font-mono text-[10px] text-ink-faint">
                  {r.note}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
