export type StateColor =
  | "green"
  | "amber"
  | "red"
  | "blue"
  | "purple"
  | "rose";

export type SnapshotState =
  | "recovered"
  | "cleared"
  | "caution"
  | "deload"
  | "autonomic-recovery-leading"
  | "peripheral-strain"
  | "illness-risk"
  | "accumulating-fatigue"
  | "insufficient_data";

/** Placeholder written before any pipeline run; not a dashboard tier label. */
export interface NoDataSnapshot {
  state: "no_data";
}

export type LoadedSnapshot = SnapshotData | NoDataSnapshot;

export interface TierBadge {
  state: StateColor;
  label: string;
}

export interface ThresholdBand {
  range: string;
  label: string;
  color: StateColor;
}

export interface Delta {
  value: number; // signed magnitude
  unit?: string; // e.g. "pts", "σ"
  vs?: string; // human-readable comparator, e.g. "yesterday", "7d avg"
}

export interface FlagshipNlrHrv {
  score: number;
  tier: "green" | "caution" | "deload" | "unknown";
  /** When scorer refused (unknown tier), show em dash instead of numeric score ring. */
  displayScore?: string;
  sparkline: number[];
  dataAgeDays: number;
  delta?: Delta;
  /**
   * Personalized prose: cites the user's actual numbers and ties them to
   * physiology. In production this is built by the scoring layer per user.
   * Rendered at the TOP of the expander, in serif body, as the lead section.
   */
  reasoning?: string;
}

export interface FlagshipSri {
  score: number;
  tier: "irregular" | "moderate" | "high" | "unknown";
  displayScore?: string;
  sparkline: number[];
  windowDays: number;
  delta?: Delta;
  reasoning?: string;
}

export interface FlagshipDecoupling {
  zscore: number;
  tier: string;
  /** When EF lens unknown — show dash instead of ±σ string. */
  displayZscore?: string;
  sparkline: number[];
  windowDays: number;
  delta?: Delta;
  reasoning?: string;
}

/**
 * A single attributable driver of a divergence — a signal that's actively
 * pulling the composite the wrong way. Renders as a labeled row inside the
 * divergence card, so the user can see *what* is driving the alert without
 * clicking ⓘ. Each driver carries a state color so it can be tinted to match
 * its severity.
 */
export interface DivergenceDriver {
  signal: string; // "NLR", "Monocytes", "HRV trend"
  value: string; // "5.37 (47 days old)"
  note: string; // "above 3.0 threshold; food-poisoning panel"
  state: StateColor;
}

/**
 * What happens when the user picks a particular answer. The card swaps the
 * question for a confirmation that quotes this payload — confidence delta,
 * actions taken, narrative headline. Without this, the prompt reads as
 * decoration; with it, answering visibly teaches the system.
 *
 * In production, the scoring layer would compute this from the answer +
 * the user's data; here it's pre-built per option for the mock.
 */
export interface DiagnosticResponse {
  /** Top-line confirmation, e.g. "Confirmed: 2026-03-14 illness window." */
  headline: string;
  /** Confidence transition, e.g. "raised from 0.78 to 0.91". */
  confidenceTransition?: string;
  /** Action implications applied to the score model going forward. */
  actions: string[];
}

export interface DiagnosticOption {
  id: string;
  label: string;
  response: DiagnosticResponse;
}

/**
 * A multiple-choice prompt the user can click on to disambiguate the
 * divergence. Improves the scoring layer's confidence without forcing them
 * to write free text. Each option carries its own response payload so the
 * card can pay off the answer immediately.
 */
export interface DiagnosticQuestion {
  prompt: string;
  options: DiagnosticOption[];
}

export interface Divergence {
  triggered: boolean;
  pattern?: string;
  interpretation?: string;
  skillRef?: string;
  reasoning?: string;
  /** What's actively pulling the composite the wrong way. */
  drivers?: DivergenceDriver[];
  /** Optional: ask the user a clarifying question to firm up confidence. */
  question?: DiagnosticQuestion;
}

export type InterventionCategory =
  | "sleep"
  | "training"
  | "recovery"
  | "nutrition";

/**
 * A projected delta on a higher-level metric if this intervention is acted
 * on. The point of carrying these on each lever is to make levers
 * *numerically comparable*: HIGH IMPACT is a label, +6 pts is a quantity.
 * It also closes the page's meta-loop — every lever ties back to a number
 * in the bio-age breakdown or the monthly composite above it.
 */
export interface InterventionProjection {
  /** Pre-formatted signed magnitude, e.g. "+6 pts". */
  value: string;
  /** What the value is on, e.g. "April composite" or "bio-age gap". */
  on: string;
}

export interface Intervention {
  action: string;
  effort: number; // 1..5
  impact: "HIGH" | "MED" | "LOW";
  category: InterventionCategory;
  why: string;
  skillRef: string;
  shortcut?: string; // optional keyboard shortcut chip, e.g. "⌘1"
  /**
   * Projected delta on the monthly composite if the user follows through.
   * Surfaced inside the impact stamp so the user can rank levers by
   * quantity, not just tier label.
   */
  projectedComposite?: InterventionProjection;
  /** Projected delta on the bio-age gap. Optional — not every lever moves it. */
  projectedBioAge?: InterventionProjection;
}

export interface MonthlyReadiness {
  score: number;
  vsLastMonth: number;
  windowLabel: string;
  meaning: string;
  reasoning?: string;
}

/**
 * One contributor to the bio-age proxy. The math is transparent:
 * sum(pullYears) ≈ (years − chronologicalYears). Each contributor carries
 * its own state color so the breakdown can be rendered as tinted bars.
 *
 * `pullYears > 0` means the signal is making the user *older* than chrono.
 * `pullYears < 0` means the signal is making them younger.
 */
export interface BioAgeContributor {
  name: string; // "Sleep Regularity"
  pullYears: number; // signed; +1.8 = pulling older
  weightPct: number; // share of total |pull| magnitude, 0..100
  detail: string; // "SRI 74 vs 80+ target"
  state: StateColor;
}

export interface BioAge {
  years: number;
  chronologicalYears: number;
  meaning: string;
  reasoning?: string;
  /** Per-component contributions to the gap, transparent and additive. */
  breakdown?: BioAgeContributor[];
}

export interface MonthlyContext {
  readiness: MonthlyReadiness;
  bioAge: BioAge;
}

/**
 * A small derived readout shown in the secondary-readouts strip. These are
 * *complementary* to The Signals — single-line, glance-only, no expander.
 * Examples: "HRV 30d", "RHR baseline shift", "Sleep debt", "Monocytes".
 */
export interface SecondaryReadout {
  label: string; // "HRV 30d"
  value: string; // "+4 ms" — pre-formatted; component just displays
  note: string; // "trending up vs March"
  state: StateColor;
}

/**
 * One day in the monthly trajectory: composite score (0..100) + tier state.
 * Two dimensions in one cell: bar HEIGHT renders the score, bar COLOR
 * renders the state. The Tufte sparkline pattern with state overlay.
 */
export interface DailyTrajectoryEntry {
  state: SnapshotState;
  /** 0-100 composite score for that day. Drives bar height. */
  score: number;
}

/**
 * Daily state + score for a calendar month, oldest first. Drives the 30-day
 * strip on the Month hero — replaces the 7-day signature, which was too
 * narrow a window for a *monthly* report.
 */
export interface MonthlyTrajectory {
  month: string; // "April 2026"
  /** Oldest → newest. Length = days in the calendar month. */
  days: DailyTrajectoryEntry[];
  /** 1-indexed day-of-month for "today" (or null if month already closed). */
  todayDayOfMonth: number | null;
}

/**
 * One month in the rolling 6-month composite history. Drives the small
 * sparkline that sits as a peer to the headline number on the Month hero,
 * giving it the trajectory anchor a Bloomberg/NEJM hero number always has.
 */
export interface MonthlyHistoryEntry {
  /** "Nov 2025" — used for tooltips. */
  month: string;
  /** Composite-readiness score for that month, 0..100. */
  score: number;
}

export interface DataStream {
  /** Internal key. */
  source: "whoop" | "amazfit" | "strava" | "jefit" | "bloodwork";
  /** Short uppercase label shown in the pill. */
  label: string;
  /** Freshness band — drives the pill dot color. */
  status: "fresh" | "stale" | "old" | "missing";
  /** Human-readable last-sync, e.g. "2h", "1d", "47d". */
  synced: string;
}

export interface SnapshotData {
  state: SnapshotState;
  score: number;
  /** When composite is insufficient_data — Today hero shows em dash, not numeric score. */
  todayScoreDisplay?: string;
  /** Δ vs yesterday, on the composite score (0-100 scale). */
  todayDelta: Delta;
  subline: string;
  action: string;
  /**
   * Personalized "why your composite is what it is today" prose. Cites the
   * user's flagship values directly. Lives on the snapshot rather than on a
   * sub-metric because it's a multi-signal explanation.
   */
  todayReasoning?: string;
  monthlyContext: MonthlyContext;
  /**
   * Full month of daily states for the Month-hero strip. Replaces the older
   * 7-day signature, which read as "the last week" rather than "the
   * reporting period". A monthly report should show the month.
   */
  monthlyTrajectory: MonthlyTrajectory;
  /**
   * Rolling 6-month monthly composites for the Month-hero peer sparkline.
   * Oldest → newest; the last entry must equal `monthlyContext.readiness`.
   */
  monthlyHistory: MonthlyHistoryEntry[];
  /**
   * @deprecated kept for the optional Today-card mini-bar; will be removed
   * once the redesign settles. The Month strip is the canonical view.
   */
  sevenDayState: SnapshotState[];
  /** Complementary scan-only readouts (HRV 30d, RHR Δ, sleep debt, …). */
  secondaryReadouts: SecondaryReadout[];
  streams: DataStream[];
  flagship: {
    nlrHrv: FlagshipNlrHrv;
    sri: FlagshipSri;
    decoupling: FlagshipDecoupling;
  };
  divergence: Divergence;
  interventions: Intervention[];
}
