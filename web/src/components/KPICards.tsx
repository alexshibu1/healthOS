import { useId, useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { COLOR_TOKENS, STATE_LABEL, STATE_TO_COLOR } from "../lib/stateColors";
import type {
  Delta,
  MonthlyContext,
  MonthlyHistoryEntry,
  MonthlyTrajectory,
  SnapshotState,
  StateColor,
} from "../types";

interface KPICardsProps {
  /* — Today (the secondary widget in this monthly report) — */
  state: SnapshotState;
  todayScore: number;
  /** Em dash headline when composite refused (e.g. insufficient_data). */

  todayScoreDisplay?: string;
  todayDelta: Delta;
  subline: string;
  action: string;
  todayReasoning?: string;
  /* — Month (the primary widget — this is a monthly report) — */
  monthlyContext: MonthlyContext;
  monthlyTrajectory: MonthlyTrajectory;
  /** 6-month rolling history for the headline-peer sparkline. */
  monthlyHistory: MonthlyHistoryEntry[];
}

/* ---------------------------------------------------------------- *
 * KPICards                                                          *
 *                                                                   *
 * Two-card row anchoring chapter I (reporting month from snapshot): *
 *   - col-7 MonthHero (primary): the headline of a monthly report  *
 *   - col-5 TodayCard (secondary): today as a check-in, not the    *
 *     centerpiece.                                                  *
 *                                                                   *
 * Inverting the visual hierarchy was the user's call: a monthly    *
 * report should put the month first and today in a sidebar. The    *
 * 30-day month strip lives on the Month hero, replacing the older  *
 * 7-day signature (which read as "last week" rather than "this     *
 * reporting period").                                               *
 * ---------------------------------------------------------------- */

export function KPICards({
  state,
  todayScore,
  todayScoreDisplay,
  todayDelta,
  subline,
  action,
  todayReasoning,
  monthlyContext,
  monthlyTrajectory,
  monthlyHistory,
}: KPICardsProps) {
  const stateLabel = STATE_LABEL[state];
  const stateTitle = titleCase(stateLabel);

  // Tier-derived color for the month: keep the same banding logic the
  // composite-spec uses. ≥75 green, ≥60 amber, else red.
  const monthColor: StateColor =
    monthlyContext.readiness.score >= 75
      ? "green"
      : monthlyContext.readiness.score >= 60
        ? "amber"
        : "red";

  return (
    <section className="mx-auto max-w-6xl px-8">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6">
        <article className="relative lg:col-span-7">
          <MonthHero
            color={monthColor}
            month={monthlyTrajectory.month}
            score={monthlyContext.readiness.score}
            delta={{
              value: monthlyContext.readiness.vsLastMonth,
              unit: "pts",
              vs: "March",
            }}
            windowLabel={monthlyContext.readiness.windowLabel}
            meaning={monthlyContext.readiness.meaning}
            reasoning={monthlyContext.readiness.reasoning}
            trajectory={monthlyTrajectory}
            history={monthlyHistory}
          />
        </article>

        <article className="relative lg:col-span-5">
          <TodayCard
            stateTitle={stateTitle}
            todayScore={todayScore}
            todayScoreDisplay={todayScoreDisplay}
            todayDelta={todayDelta}
            subline={subline}
            action={action}
            todayReasoning={todayReasoning}
          />
        </article>
      </div>
    </section>
  );
}

function titleCase(label: string): string {
  return label
    .toLowerCase()
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/* ---------------------------------------------------------------- *
 * MonthHero — the primary card in a monthly report                 *
 * ---------------------------------------------------------------- */

interface MonthHeroProps {
  color: StateColor;
  month: string;
  score: number;
  delta: Delta;
  windowLabel: string;
  meaning: string;
  reasoning?: string;
  trajectory: MonthlyTrajectory;
  history: MonthlyHistoryEntry[];
}

function MonthHero({
  color,
  month,
  score,
  delta,
  windowLabel,
  meaning,
  reasoning,
  trajectory,
  history,
}: MonthHeroProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanderId = useId();
  const tokens = COLOR_TOKENS[color];

  const tierLabel =
    score >= 75 ? "GREEN" : score >= 60 ? "CAUTION" : "DELOAD";

  const deltaArrow = delta.value > 0 ? "↗" : delta.value < 0 ? "↘" : "→";
  const deltaSign = delta.value > 0 ? "+" : "";

  return (
    <div className="group relative h-full overflow-hidden rounded-md border border-paper-divider bg-paper p-8 shadow-card transition-shadow hover:shadow-card-hover">
      {/* Card label — month name + window + ⓘ */}
      <div className="flex items-baseline justify-between border-b border-paper-divider pb-3">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
            Reporting period
          </span>
          <span className="font-mono tabular text-[10px] text-ink-faint">
            {windowLabel}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          aria-expanded={isExpanded}
          aria-controls={expanderId}
          aria-label={
            isExpanded ? "Collapse month details" : "Explain this month"
          }
          className="inline-flex h-5 w-5 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-paper-tinted hover:text-ink"
        >
          <span aria-hidden className="text-[14px] leading-none">
            {isExpanded ? "−" : "ⓘ"}
          </span>
        </button>
      </div>

      {/* Headline: month name (serif), score, peer sparkline, delta, tier */}
      <div className="mt-7">
        <h1 className="display text-chapter font-light leading-[1.05] text-ink">
          {month}
        </h1>
        {/* Score row + wider 6-mo trajectory (readable at a glance vs squinting
            at a 64px micro-sparkline). Threshold guides anchor the amber band. */}
        <div className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-8">
          <div className="flex shrink-0 items-end gap-5">
            <span className="display tabular text-hero font-light leading-none text-ink">
              {score}
            </span>
            <span className="display text-2xl font-light leading-none text-ink-subtle">
              / 100
            </span>
          </div>
          <div className="min-w-0 flex-1 lg:max-w-md xl:max-w-lg">
            <span className="mb-2 block font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-ink-subtle">
              Six-month composite
            </span>
            <MonthlyHistorySparkline
              data={history}
              accentColor={tokens.spark}
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className={`h-1.5 w-1.5 rounded-full ${tokens.dot}`}
            />
            <span
              className={`font-mono text-[10px] font-medium uppercase tracking-[0.18em] ${tokens.ink}`}
            >
              {tierLabel} BAND
            </span>
          </span>
          <span
            className={`font-mono tabular text-[11px] ${
              delta.value > 0
                ? "text-state-green-ink"
                : delta.value < 0
                  ? "text-state-red-ink"
                  : "text-ink-faint"
            }`}
          >
            {deltaArrow} {deltaSign}
            {delta.value} {delta.unit} vs {delta.vs}
          </span>
        </div>
        <p className="display mt-5 max-w-lg text-base font-light leading-relaxed text-ink-muted">
          {meaning}
        </p>
      </div>

      {/* 30-day month strip — the headline visualization. One cell per day,
          colored by that day's state. Today is the rightmost cell. */}
      <div className="mt-7 border-t border-paper-divider pt-5">
        <div className="mb-2.5 flex items-baseline justify-between">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
            Daily trajectory
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">
            day 1 → today
          </span>
        </div>
        <MonthStrip trajectory={trajectory} />
        <MonthStripLegend trajectory={trajectory} />
      </div>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            id={expanderId}
            key="month-expander"
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
              {reasoning && (
                <ExpanderSection title="Why this matters for you">
                  <p className="display text-[15px] font-light leading-relaxed text-ink">
                    {reasoning}
                  </p>
                </ExpanderSection>
              )}
              <ExpanderSection title="How it's computed">
                <p className="text-sm leading-relaxed text-ink-muted">
                  Mean of daily composite-readiness scores across the
                  calendar month, weighted by data completeness for that
                  day. The 30-day strip above is the same daily series
                  colored by tier band.
                </p>
              </ExpanderSection>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
                skill composite-spec §3
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ---------------------------------------------------------------- *
 * MonthlyHistorySparkline — multi-month composite trajectory        *
 *                                                                   *
 * Wider responsive SVG (viewBox) + labeled months + optional        *
 * dashed guides at 75 / 60 so the caution / green split is legible. *
 * ---------------------------------------------------------------- */

const SPARK_VB_W = 280;
const SPARK_VB_H = 56;
const SPARK_PAD_X = 10;
const SPARK_TOP = 10;
const SPARK_BOTTOM = 44;

function MonthlyHistorySparkline({
  data,
  accentColor,
}: {
  data: MonthlyHistoryEntry[];
  accentColor: string;
}) {
  if (!data || data.length < 2) return null;

  const scores = data.map((d) => d.score);
  const minS = Math.min(...scores);
  const maxS = Math.max(...scores);
  // Stretch domain so tier boundaries (60 / 75) often appear as context.
  let vmin = Math.min(minS, 60) - 6;
  let vmax = Math.max(maxS, 75) + 4;
  vmin = Math.max(0, vmin);
  vmax = Math.min(100, Math.max(vmax, vmin + 8));
  const vrange = vmax - vmin || 1;

  const yAt = (scoreValue: number) =>
    SPARK_TOP + (1 - (scoreValue - vmin) / vrange) * (SPARK_BOTTOM - SPARK_TOP);

  const guides = [75, 60].filter((g) => g >= vmin && g <= vmax);

  const points = data.map((d, i) => {
    const x =
      SPARK_PAD_X +
      (i / (data.length - 1)) * (SPARK_VB_W - 2 * SPARK_PAD_X);
    const y = yAt(d.score);
    return { x, y, score: d.score, month: d.month };
  });

  const path = points
    .map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`))
    .join(" ");
  const last = points[points.length - 1];

  const ariaMonths = data.map((d) => d.month).join(" → ");

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${SPARK_VB_W} ${SPARK_VB_H}`}
        className="h-14 w-full sm:h-16"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Monthly composite trend ${ariaMonths}; current ${last.score}`}
      >
        <title>{`Monthly composites: ${scores.join(", ")} ending at ${last.score}`}</title>
        {/* Baseline / band guides */}
        {guides.map((g) => (
          <line
            key={g}
            x1={SPARK_PAD_X}
            x2={SPARK_VB_W - SPARK_PAD_X}
            y1={yAt(g)}
            y2={yAt(g)}
            stroke="currentColor"
            strokeWidth={0.85}
            strokeDasharray="4 3"
            className="text-ink-faint/50"
          />
        ))}
        {/* Main trend */}
        <path
          d={path}
          stroke={accentColor}
          strokeWidth={2}
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        {points.map((p, i) => (
          <circle
            key={`${p.month}-${i}`}
            cx={p.x}
            cy={p.y}
            r={i === points.length - 1 ? 4 : 2.75}
            fill={i === points.length - 1 ? accentColor : "#fff"}
            stroke={accentColor}
            strokeWidth={i === points.length - 1 ? 0 : 1.35}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className="mt-2 flex w-full justify-between gap-1 font-mono text-[9px] uppercase leading-none tracking-[0.08em] text-ink-faint sm:text-[10px]">
        {data.map((d) => (
          <span key={d.month} className="min-w-0 flex-1 truncate text-center">
            {shortMonth(d.month)}
          </span>
        ))}
      </div>
      {guides.length > 0 && (
        <p className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint/80">
          Dotted guides: 75 (green target) · 60 (caution floor)
        </p>
      )}
    </div>
  );
}

function shortMonth(label?: string): string {
  if (!label) return "";
  // "Nov 2025" → "Nov" — keeps the legend ends compact
  return label.split(" ")[0] ?? label;
}

/* ---------------------------------------------------------------- *
 * MonthStrip — 30 baseline-aligned bars, height = score, color = state *
 *                                                                   *
 * Two dimensions, same footprint:                                   *
 *   - HEIGHT encodes the day's composite score (0..100).            *
 *   - COLOR encodes the state band (cleared / caution / deload / …) *
 *                                                                   *
 * Bars hug a shared baseline (items-end) so taller = better, no    *
 * exception. The Tufte-sparkline + state-overlay idiom in 30 cells. *
 * ---------------------------------------------------------------- */

const STRIP_MIN_PX = 6; // floor so even score-0 still has a visible cell
const STRIP_MAX_PX = 44;

function scoreToHeight(score: number): number {
  const clamped = Math.max(0, Math.min(100, score));
  return STRIP_MIN_PX + (clamped / 100) * (STRIP_MAX_PX - STRIP_MIN_PX);
}

function MonthStrip({ trajectory }: { trajectory: MonthlyTrajectory }) {
  const { days, todayDayOfMonth } = trajectory;
  const monthShort = trajectory.month.split(" ")[0];

  // Bars and labels render in two parallel flex rows so every bar shares
  // the same baseline regardless of whether its column carries an anchor
  // day-label. Mixing bar+label inside a single flex column would shift
  // the baseline up on label-bearing days, breaking the bar-chart frame.
  return (
    <div
      role="img"
      aria-label={`Daily score and state for each of ${days.length} days in ${trajectory.month}`}
    >
      {/* Row 1 — bars. items-end pins to the shared baseline. */}
      <div
        className="flex items-end gap-[2px]"
        style={{ height: STRIP_MAX_PX }}
      >
        {days.map((entry, i) => {
          const dayColor = STATE_TO_COLOR[entry.state];
          const dayTokens = COLOR_TOKENS[dayColor];
          const dayNum = i + 1;
          const isToday = dayNum === todayDayOfMonth;
          const heightPx = scoreToHeight(entry.score);
          return (
            <div
              key={i}
              className="flex flex-1 justify-center"
              style={{ height: `${heightPx}px` }}
              title={`${monthShort} ${dayNum}: score ${entry.score}, ${STATE_LABEL[entry.state]}`}
            >
              <div
                className="w-full rounded-sm"
                style={{
                  backgroundColor: isToday
                    ? dayTokens.spark + "40"
                    : dayTokens.spark + "26",
                  borderTop: `${isToday ? 3 : 2}px solid ${dayTokens.spark}`,
                  boxShadow: isToday
                    ? `inset 0 0 0 1px ${dayTokens.spark}66`
                    : undefined,
                }}
              />
            </div>
          );
        })}
      </div>
      {/* Row 2 — anchor day labels (1, 10, 20, last). Each cell is the
          same width as its bar above so labels align by column. */}
      <div className="mt-1 flex gap-[2px]">
        {days.map((_, i) => {
          const dayNum = i + 1;
          const isAnchor =
            dayNum === 1 ||
            dayNum === 10 ||
            dayNum === 20 ||
            dayNum === days.length;
          const isToday = dayNum === todayDayOfMonth;
          return (
            <div key={i} className="flex-1 text-center">
              {isAnchor && (
                <span
                  className={`font-mono tabular text-[9px] ${
                    isToday ? "text-ink-muted" : "text-ink-faint"
                  }`}
                >
                  {dayNum}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MonthStripLegend({ trajectory }: { trajectory: MonthlyTrajectory }) {
  // Count occurrences per state so the legend doubles as a quick tally.
  const counts = trajectory.days.reduce<Record<string, number>>((acc, e) => {
    acc[e.state] = (acc[e.state] || 0) + 1;
    return acc;
  }, {});
  const order: SnapshotState[] = [
    "insufficient_data",
    "accumulating-fatigue",
    "cleared",
    "recovered",
    "autonomic-recovery-leading",
    "caution",
    "deload",
    "peripheral-strain",
    "illness-risk",
  ];
  const present = order.filter((s) => counts[s]);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {present.map((s) => {
        const c = COLOR_TOKENS[STATE_TO_COLOR[s]];
        return (
          <span key={s} className="inline-flex items-center gap-1.5">
            <span aria-hidden className={`h-1 w-1 rounded-full ${c.dot}`} />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-subtle">
              {STATE_LABEL[s]}
            </span>
            <span className="font-mono tabular text-[10px] text-ink-faint">
              {counts[s]}d
            </span>
          </span>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------- *
 * TodayCard — the secondary widget                                  *
 * ---------------------------------------------------------------- */

interface TodayCardProps {
  stateTitle: string;
  todayScore: number;

  /** When composite cannot emit numeric headline (insufficient inputs). */


  todayScoreDisplay?: string;
  todayDelta: Delta;
  subline: string;
  action: string;
  todayReasoning?: string;
}

function TodayCard({
  stateTitle,
  todayScore,
  todayScoreDisplay,
  todayDelta,
  subline,
  action,
  todayReasoning,
}: TodayCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanderId = useId();

  const deltaArrow =
    todayDelta.value > 0 ? "↗" : todayDelta.value < 0 ? "↘" : "→";
  const deltaSign = todayDelta.value > 0 ? "+" : "";

  return (
    <div className="group relative h-full overflow-hidden rounded-md border border-paper-divider bg-paper p-7 shadow-card transition-shadow hover:shadow-card-hover">
      <div className="flex items-baseline justify-between border-b border-paper-divider pb-3">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
          Today
        </span>
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          aria-expanded={isExpanded}
          aria-controls={expanderId}
          aria-label={
            isExpanded ? "Collapse Today details" : "Explain Today"
          }
          className="inline-flex h-5 w-5 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-paper-tinted hover:text-ink"
        >
          <span aria-hidden className="text-[14px] leading-none">
            {isExpanded ? "−" : "ⓘ"}
          </span>
        </button>
      </div>

      {/* Score row — smaller than the Month hero, this is a sidebar */}
      <div className="mt-6 flex items-baseline gap-3">
        <span className="display tabular text-card font-light leading-none text-ink">
          {todayScoreDisplay ?? todayScore}
        </span>
        {!todayScoreDisplay ? (
          <span className="display text-base font-light text-ink-subtle">
            / 100
          </span>
        ) : null}
        <span
          className={`ml-auto font-mono tabular text-[10px] ${
            todayDelta.value > 0
              ? "text-state-green-ink"
              : todayDelta.value < 0
                ? "text-state-red-ink"
                : "text-ink-faint"
          }`}
        >
          {deltaArrow} {deltaSign}
          {todayDelta.value} {todayDelta.unit}
        </span>
      </div>

      {/* State title + ONE short sentence. The fuller subline + action +
          reasoning live in the ⓘ expander — preserves the layered-
          disclosure pattern that the secondary widget had broken. */}
      <h2 className="display mt-5 text-2xl font-light leading-tight text-ink">
        {stateTitle}
      </h2>
      <p className="display mt-3 text-base font-light leading-relaxed text-ink">
        {subline}
      </p>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            id={expanderId}
            key="today-expander"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: 0.22,
              ease: [0.32, 0.72, 0, 1],
            }}
            className="overflow-hidden"
          >
            <div className="mt-5 space-y-4 border-t border-paper-divider pt-4">
              {todayReasoning && (
                <ExpanderSection title="Why your score is what it is">
                  <p className="display text-[14px] font-light leading-relaxed text-ink">
                    {todayReasoning}
                  </p>
                </ExpanderSection>
              )}
              <ExpanderSection title="Today's action — full version">
                <p className="text-sm leading-relaxed text-ink-muted">
                  {action}
                </p>
              </ExpanderSection>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
                skill §4 (divergence matrix)
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ---------------------------------------------------------------- *
 * shared expander section helper                                    *
 * ---------------------------------------------------------------- */

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
