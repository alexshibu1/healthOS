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
  | "illness-risk";

export interface TierBadge {
  state: StateColor;
  label: string;
}

export interface ThresholdBand {
  range: string;
  label: string;
  color: StateColor;
}

export interface FlagshipNlrHrv {
  score: number;
  tier: "green" | "caution" | "deload";
  sparkline: number[];
  dataAgeDays: number;
}

export interface FlagshipSri {
  score: number;
  tier: "irregular" | "moderate" | "high";
  sparkline: number[];
  windowDays: number;
}

export interface FlagshipDecoupling {
  zscore: number;
  tier: string;
  sparkline: number[];
  windowDays: number;
}

export interface Divergence {
  triggered: boolean;
  pattern?: string;
  interpretation?: string;
  skillRef?: string;
}

export interface Intervention {
  action: string;
  effort: number;
  impact: "HIGH" | "MED" | "LOW";
  why: string;
  skillRef: string;
}

export interface MonthlyReadiness {
  score: number;
  vsLastMonth: number;
  windowLabel: string;
  meaning: string;
}

export interface BioAge {
  years: number;
  chronologicalYears: number;
  meaning: string;
}

export interface MonthlyContext {
  readiness: MonthlyReadiness;
  bioAge: BioAge;
}

export interface SnapshotData {
  state: SnapshotState;
  score: number;
  subline: string;
  action: string;
  monthlyContext: MonthlyContext;
  flagship: {
    nlrHrv: FlagshipNlrHrv;
    sri: FlagshipSri;
    decoupling: FlagshipDecoupling;
  };
  divergence: Divergence;
  interventions: Intervention[];
}
