import { MetricPrimer } from "./MetricPrimer";
import { FLAGSHIP_TIER_TO_COLOR } from "../lib/stateColors";
import type {
  FlagshipNlrHrv,
  FlagshipSri,
  FlagshipDecoupling,
  StateColor,
} from "../types";

interface FlagshipCardsProps {
  nlrHrv: FlagshipNlrHrv;
  sri: FlagshipSri;
  decoupling: FlagshipDecoupling;
}

export function FlagshipCards({
  nlrHrv,
  sri,
  decoupling,
}: FlagshipCardsProps) {
  const nlrColor = FLAGSHIP_TIER_TO_COLOR[nlrHrv.tier] as StateColor;
  const sriColor = FLAGSHIP_TIER_TO_COLOR[sri.tier] as StateColor;
  const decoupColor =
    decoupling.zscore >= 1
      ? "red"
      : decoupling.zscore >= 0
        ? "amber"
        : "green";

  return (
    <section className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-8 pb-6 md:grid-cols-3">
      <MetricPrimer
        variant="card"
        label="NLR × HRV"
        value={nlrHrv.score.toFixed(2)}
        tier={{ state: nlrColor, label: nlrHrv.tier.toUpperCase() }}
        thresholdContext={
          nlrHrv.score >= 1.5
            ? "↑ above 1.5 deload threshold"
            : nlrHrv.score >= 1.0
              ? "↑ in 1.0–1.5 caution band"
              : "↓ below 1.0 — green"
        }
        meaning="Inflammation is outpacing autonomic recovery. The wearable's improving HRV is the lymphocyte side recovering before the neutrophil side has."
        sparkline={nlrHrv.sparkline}
        dataAge={`CBC drawn ${nlrHrv.dataAgeDays}d ago`}
        formula="NLR ÷ 3.0 × (7-day HRV baseline ÷ today's HRV). Each side above 1.0 means you're off the baseline; multiplying them amplifies agreement and dampens single-system divergences."
        thresholdBands={[
          { range: "< 1.0", label: "Green — train normally", color: "green" },
          {
            range: "1.0 – 1.5",
            label: "Caution — cap at Zone 2",
            color: "amber",
          },
          { range: "≥ 1.5", label: "Deload — hold intensity", color: "red" },
        ]}
        mechanism="Neutrophils track the stress arm of your nervous system; lymphocytes (and HRV) track the recovery arm. Together they measure both push and pull at once — a fusion no single-source consumer app can compute. Cited in skill §1.1 (Sternal & Kalinkovich; Aeschbacher 2017)."
        skillRef="§1"
      />

      <MetricPrimer
        variant="card"
        label="Sleep Regularity"
        value={sri.score}
        tier={{ state: sriColor, label: sri.tier.toUpperCase() }}
        thresholdContext={
          sri.score < 70
            ? "↓ below 70 — irregular"
            : sri.score < 80
              ? "↓ below 80 — moderate"
              : "↑ above 80 — high"
        }
        meaning="Sleep timing varies night-to-night enough to add measurable circadian drag, even though total hours look fine."
        sparkline={sri.sparkline}
        dataAge={`window ${sri.windowDays}d`}
        formula="Phillips SRI: percentage of consecutive minute-pairs where you were in the same sleep/wake state at the same clock time on adjacent days. Range 0 (random) to 100 (identical timing)."
        thresholdBands={[
          { range: "≥ 80", label: "High regularity", color: "green" },
          { range: "70 – 80", label: "Moderate", color: "amber" },
          { range: "< 70", label: "Irregular — risk band", color: "red" },
        ]}
        mechanism="Regularity is independent of duration. Windred 2024 (UK Biobank, n=60,977) found SRI < 70 associated with 20–48% higher all-cause mortality and was a stronger predictor than sleep duration. Cited in skill §2.4."
        skillRef="§2"
      />

      <MetricPrimer
        variant="card"
        label="Aerobic Decoupling"
        value={`${decoupling.zscore >= 0 ? "+" : ""}${decoupling.zscore.toFixed(1)}σ`}
        tier={{
          state: decoupColor,
          label: decoupling.tier.toUpperCase(),
        }}
        thresholdContext={
          decoupling.zscore >= 1
            ? "↑ above +1σ — fraying"
            : decoupling.zscore >= 0
              ? "↑ above baseline"
              : "↓ below baseline — adapted"
        }
        meaning="Aerobic economy is slipping vs your 30-day Zone 2 baseline — the same pace is costing more heart-rate."
        sparkline={decoupling.sparkline}
        dataAge={`window ${decoupling.windowDays}d`}
        formula="Today's efficiency factor (pace ÷ HR) on Z2 effort, z-scored against your rolling 30-day mean and SD on comparable sessions."
        thresholdBands={[
          { range: "< 0σ", label: "Adapted — improving", color: "green" },
          { range: "0 – 1σ", label: "Drifting — monitor", color: "amber" },
          { range: "≥ 1σ", label: "Fraying — investigate", color: "red" },
        ]}
        mechanism="When the heart drifts up at the same pace, something is leaking efficiency: hydration, heat, fatigue, or fitness slipping. Sustained z > 0 over 5 days is an early signal that precedes felt symptoms. Cited in skill §3 (González-Alonso & Coyle 1992)."
        skillRef="§3"
      />
    </section>
  );
}
