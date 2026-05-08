import { MetricPrimer } from "./MetricPrimer";
import { STATE_LABEL, STATE_TO_COLOR } from "../lib/stateColors";
import type { SnapshotState } from "../types";

interface StateHeroProps {
  state: SnapshotState;
  score: number;
  subline: string;
  action: string;
}

export function StateHero({ state, score, subline, action }: StateHeroProps) {
  const stateColor = STATE_TO_COLOR[state];
  const stateLabel = STATE_LABEL[state];

  return (
    <section className="mx-auto max-w-6xl px-8 pb-6">
      <MetricPrimer
        variant="hero"
        label={stateLabel}
        value={score}
        tier={{ state: stateColor, label: stateLabel }}
        meaning={subline}
        action={action}
        formula="Composite of NLR × HRV (inflammatory + autonomic), Sleep Regularity Index (chronobiological), and Aerobic Decoupling (peripheral / thermoregulatory). The named state comes from the divergence matrix in skill §4 — it tells you which lenses agree and which disagree."
        thresholdBands={[
          { range: "≥ 75", label: "Green — train normally", color: "green" },
          { range: "50–75", label: "Caution — cap intensity", color: "amber" },
          { range: "< 50", label: "Deload — rest priority", color: "red" },
        ]}
        mechanism="When the three flagship metrics disagree, the disagreement itself is the diagnostic signal. The state name above is what skill §1.2 / §4 calls today's specific pattern — not just the score, but the underlying physiological story behind it. The bridge sentence above translates the pattern to plain English so you don't need the jargon to act on it."
        skillRef="§4 (divergence matrix)"
      />
    </section>
  );
}
