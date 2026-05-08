import { MetricPrimer } from "./MetricPrimer";
import type { MonthlyContext } from "../types";

interface ContextStripProps {
  context: MonthlyContext;
}

export function ContextStrip({ context }: ContextStripProps) {
  const { readiness, bioAge } = context;
  const trendArrow = readiness.vsLastMonth >= 0 ? "↗" : "↘";
  const trendSign = readiness.vsLastMonth >= 0 ? "+" : "";

  return (
    <section className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-8 py-6 md:grid-cols-2">
      <MetricPrimer
        variant="card"
        label="This month's readiness"
        value={readiness.score}
        tier={{ state: "blue", label: readiness.windowLabel }}
        meaning={readiness.meaning}
        thresholdContext={`${trendArrow} ${trendSign}${readiness.vsLastMonth} vs last month`}
        formula="Arithmetic mean of daily composite-readiness scores across the calendar month, weighted by data completeness for that day."
        thresholdBands={[
          { range: "≥ 75", label: "Strong month", color: "green" },
          { range: "60–75", label: "Steady, monitor", color: "amber" },
          { range: "< 60", label: "Stress accumulating", color: "red" },
        ]}
        mechanism="A monthly average smooths out single-day noise and shows whether you're adapting or accumulating stress. The direction of travel matters more than the absolute number — a 64 trending up is healthier than a 70 trending down."
        skillRef="composite-spec §3"
      />
      <MetricPrimer
        variant="card"
        label="Bio-age proxy"
        value={`${bioAge.years}y`}
        tier={{
          state: bioAge.years > bioAge.chronologicalYears ? "amber" : "green",
          label: `vs chronological ${bioAge.chronologicalYears}y`,
        }}
        meaning={bioAge.meaning}
        thresholdContext="Illustrative only — not a medical estimate."
        formula="Weighted blend of HRV-trend percentile, sleep-regularity score, and resting HR baseline, mapped to a population age-equivalent."
        thresholdBands={[
          {
            range: "below chrono",
            label: "Tracking ahead",
            color: "green",
          },
          {
            range: "± 2 yrs",
            label: "On pace",
            color: "blue",
          },
          {
            range: "above chrono",
            label: "Lifestyle drag",
            color: "amber",
          },
        ]}
        mechanism="The number tells you whether your physiology is tracking ahead, behind, or with your chronological age. The biggest movers are usually sleep regularity and HRV trend; isolated bad days don't shift it. Bigger gaps require bigger lifestyle moves to close."
        skillRef="bio-age-spec §1"
      />
    </section>
  );
}
