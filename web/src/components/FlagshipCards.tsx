import { useId, useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { RingMeter } from "./RingMeter";
import { COLOR_TOKENS, FLAGSHIP_TIER_TO_COLOR } from "../lib/stateColors";
import type {
  Delta,
  FlagshipNlrHrv,
  FlagshipSri,
  FlagshipDecoupling,
  StateColor,
  ThresholdBand,
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
  const decoupColor: StateColor =
    decoupling.zscore >= 1
      ? "red"
      : decoupling.zscore >= 0
        ? "amber"
        : "green";

  // severity-based fill — more fill = louder signal regardless of metric direction
  const nlrFill = clamp((nlrHrv.score / 2.0) * 100, 0, 100);
  const sriFill = clamp(((100 - sri.score) / 50) * 100, 0, 100);
  const decoupFill = clamp((Math.abs(decoupling.zscore) / 2.0) * 100, 0, 100);

  return (
    <section className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-8 md:grid-cols-3 md:gap-6">
      <FlagshipCard
        label="NLR × HRV"
        ordinal="01"
        color={nlrColor}
        ringValue={nlrFill}
        thresholdTicks={[50, 75]}
        ringDisplay={
          <span className="display tabular text-card font-light text-ink">
            {nlrHrv.score.toFixed(2)}
          </span>
        }
        tierLabel={nlrHrv.tier.toUpperCase()}
        thresholdContext={
          nlrHrv.score >= 1.5
            ? "above 1.5 deload threshold"
            : nlrHrv.score >= 1.0
              ? "in 1.0–1.5 caution band"
              : "below 1.0 — green"
        }
        delta={nlrHrv.delta}
        meaning="Inflammation outpacing autonomic recovery — improving HRV is the lymphocyte side recovering before the neutrophil side has."
        sparkline={nlrHrv.sparkline}
        sparklineRange={{
          min: Math.min(...nlrHrv.sparkline),
          max: Math.max(...nlrHrv.sparkline),
        }}
        dataAge={`CBC ${nlrHrv.dataAgeDays}d`}
        reasoning={nlrHrv.reasoning}
        formula="NLR ÷ 3.0 × (7-day HRV baseline ÷ today's HRV). Each side above 1.0 means you're off baseline; multiplying amplifies agreement and dampens single-system divergences."
        thresholdBands={[
          { range: "< 1.0", label: "Green — train normally", color: "green" },
          { range: "1.0 – 1.5", label: "Caution — cap at Z2", color: "amber" },
          { range: "≥ 1.5", label: "Deload — hold intensity", color: "red" },
        ]}
        mechanism="Neutrophils track the stress arm of your nervous system; lymphocytes (and HRV) track the recovery arm. Together they measure both push and pull at once — a fusion no single-source consumer app can compute. Cited in skill §1.1 (Sternal & Kalinkovich; Aeschbacher 2017)."
        skillRef="§1"
      />

      <FlagshipCard
        label="Sleep Regularity"
        ordinal="02"
        color={sriColor}
        ringValue={sriFill}
        thresholdTicks={[40, 60]}
        ringDisplay={
          <span className="display tabular text-card font-light text-ink">
            {sri.score}
          </span>
        }
        tierLabel={sri.tier.toUpperCase()}
        thresholdContext={
          sri.score < 70
            ? "below 70 — irregular"
            : sri.score < 80
              ? "below 80 — moderate"
              : "above 80 — high"
        }
        delta={sri.delta}
        meaning="Sleep timing varies night-to-night enough to add measurable circadian drag, even though total hours look fine."
        sparkline={sri.sparkline}
        sparklineRange={{
          min: Math.min(...sri.sparkline),
          max: Math.max(...sri.sparkline),
        }}
        dataAge={`window ${sri.windowDays}d`}
        reasoning={sri.reasoning}
        formula="Phillips SRI: percentage of consecutive minute-pairs where you were in the same sleep/wake state at the same clock time on adjacent days. Range 0 (random) to 100 (identical timing)."
        thresholdBands={[
          { range: "≥ 80", label: "High regularity", color: "green" },
          { range: "70 – 80", label: "Moderate", color: "amber" },
          { range: "< 70", label: "Irregular — risk band", color: "red" },
        ]}
        mechanism="Regularity is independent of duration. Windred 2024 (UK Biobank, n=60,977) found SRI < 70 associated with 20–48% higher all-cause mortality and stronger as a predictor than sleep duration. Cited in skill §2.4."
        skillRef="§2"
      />

      <FlagshipCard
        label="Aerobic Decoupling"
        ordinal="03"
        color={decoupColor}
        ringValue={decoupFill}
        thresholdTicks={[50, 75]}
        ringDisplay={
          <span className="display tabular text-card font-light text-ink">
            {`${decoupling.zscore >= 0 ? "+" : ""}${decoupling.zscore.toFixed(1)}σ`}
          </span>
        }
        tierLabel={decoupling.tier.toUpperCase()}
        thresholdContext={
          decoupling.zscore >= 1
            ? "above +1σ — fraying"
            : decoupling.zscore >= 0
              ? "above baseline"
              : "below baseline — adapted"
        }
        delta={decoupling.delta}
        meaning="Aerobic economy slipping vs your 30-day Zone 2 baseline — the same pace is costing more heart-rate."
        sparkline={decoupling.sparkline}
        sparklineRange={{
          min: Math.min(...decoupling.sparkline),
          max: Math.max(...decoupling.sparkline),
        }}
        dataAge={`window ${decoupling.windowDays}d`}
        reasoning={decoupling.reasoning}
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

interface FlagshipCardProps {
  label: string;
  ordinal: string;
  color: StateColor;
  ringValue: number;
  thresholdTicks?: number[];
  ringDisplay: ReactNode;
  tierLabel: string;
  thresholdContext: string;
  delta?: Delta;
  meaning: string;
  sparkline: number[];
  sparklineRange: { min: number; max: number };
  dataAge: string;
  /**
   * Personalized prose: the user's actual numbers + what they imply for THIS
   * person right now. Lead section of the expander, in serif body — visual
   * primacy over the generic mechanism / formula.
   */
  reasoning?: string;
  formula: string;
  thresholdBands: ThresholdBand[];
  mechanism: string;
  skillRef: string;
}

function FlagshipCard({
  label,
  ordinal,
  color,
  ringValue,
  thresholdTicks,
  ringDisplay,
  tierLabel,
  thresholdContext,
  delta,
  meaning,
  sparkline,
  sparklineRange,
  dataAge,
  reasoning,
  formula,
  thresholdBands,
  mechanism,
  skillRef,
}: FlagshipCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanderId = useId();
  const tokens = COLOR_TOKENS[color];

  return (
    <div className="group relative overflow-hidden rounded-md border border-paper-divider bg-paper p-6 shadow-card transition-shadow hover:shadow-card-hover">
      {/* Card header — same hairline-rule treatment as KPI cards */}
      <div className="flex items-baseline justify-between border-b border-paper-divider pb-3">
        <div className="flex items-baseline gap-3">
          <span className="font-mono tabular text-[10px] font-medium text-ink-faint">
            {ordinal}
          </span>
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
            {label}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          aria-expanded={isExpanded}
          aria-controls={expanderId}
          aria-label={
            isExpanded
              ? `Collapse ${label} details`
              : `Explain ${label} in detail`
          }
          className="inline-flex h-5 w-5 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-paper-tinted hover:text-ink"
        >
          <span aria-hidden className="text-[14px] leading-none">
            {isExpanded ? "−" : "ⓘ"}
          </span>
        </button>
      </div>

      {/* Ring + tier */}
      <div className="mt-5 flex items-start gap-5">
        <RingMeter
          color={color}
          size="sm"
          value={ringValue}
          thresholdTicks={thresholdTicks}
        >
          {ringDisplay}
        </RingMeter>
        <div className="flex-1 pt-1">
          <div className="flex items-center gap-2">
            <span className={`h-1 w-1 rounded-full ${tokens.dot}`} />
            <span
              className={`font-mono text-[10px] font-medium uppercase tracking-[0.18em] ${tokens.ink}`}
            >
              {tierLabel}
            </span>
          </div>
          <div className="mt-1.5 display text-sm font-light text-ink-muted">
            {thresholdContext}
          </div>
          {delta && (
            <div
              className={`mt-1 font-mono tabular text-[10px] ${
                delta.value > 0
                  ? "text-state-green-ink"
                  : delta.value < 0
                    ? "text-state-red-ink"
                    : "text-ink-faint"
              }`}
            >
              {delta.value > 0 ? "↗" : delta.value < 0 ? "↘" : "→"}{" "}
              {delta.value > 0 ? "+" : ""}
              {delta.value}
              {delta.unit ?? ""} vs {delta.vs}
            </div>
          )}
        </div>
      </div>

      <p className="display mt-4 text-sm font-light leading-relaxed text-ink-muted">
        {meaning}
      </p>

      {/* Sparkline + axis labels */}
      <div className="mt-5">
        <div className="h-10">
          <Sparkline data={sparkline} color={tokens.spark} />
        </div>
        <div className="mt-1 flex justify-between font-mono tabular text-[10px] text-ink-faint">
          <span>min {sparklineRange.min.toFixed(2)}</span>
          <span>max {sparklineRange.max.toFixed(2)}</span>
        </div>
      </div>

      <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
        {dataAge}
      </div>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            id={expanderId}
            key="flagship-expander"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: 0.22,
              ease: [0.32, 0.72, 0, 1],
            }}
            className="overflow-hidden"
          >
            <div className="mt-5 space-y-5 border-t border-paper-divider pt-5">
              {/* 1. Why this matters for YOU — personalized lead, serif,
                  full ink, larger size. The most important section. */}
              {reasoning && (
                <ExpanderSection title="Why this matters for you">
                  <p className="display text-[15px] font-light leading-relaxed text-ink">
                    {reasoning}
                  </p>
                </ExpanderSection>
              )}
              {/* 2. What it measures — generic physiology, kept for
                  educational context. Sans, muted, smaller. */}
              <ExpanderSection title="What it measures">
                <p className="text-sm leading-relaxed text-ink-muted">
                  {mechanism}
                </p>
              </ExpanderSection>
              {/* 3. Threshold bands. */}
              <ExpanderSection title="Threshold bands">
                <ul className="space-y-1.5 text-sm text-ink-muted">
                  {thresholdBands.map((band) => {
                    const bt = COLOR_TOKENS[band.color];
                    return (
                      <li
                        key={band.range}
                        className="flex items-center gap-3"
                      >
                        <span
                          className={`inline-block h-1 w-1 rounded-full ${bt.dot}`}
                        />
                        <span className="font-mono tabular w-20 text-xs text-ink-subtle">
                          {band.range}
                        </span>
                        <span className="display font-light">
                          {band.label}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </ExpanderSection>
              {/* 4. How it's computed — formula, last. */}
              <ExpanderSection title="How it's computed">
                <p className="text-sm leading-relaxed text-ink-muted">
                  {formula}
                </p>
              </ExpanderSection>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
                skill {skillRef}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
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

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const points = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart
        data={points}
        margin={{ top: 2, right: 2, bottom: 2, left: 2 }}
      >
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.75}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, x));
}
