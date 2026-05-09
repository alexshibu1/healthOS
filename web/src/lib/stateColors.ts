import type { SnapshotState, StateColor } from "../types";

export const STATE_TO_COLOR: Record<SnapshotState, StateColor> = {
  recovered: "green",
  cleared: "green",
  caution: "amber",
  deload: "red",
  "autonomic-recovery-leading": "blue",
  "peripheral-strain": "purple",
  "illness-risk": "rose",
  "accumulating-fatigue": "amber",
  insufficient_data: "amber",
};

export const STATE_LABEL: Record<SnapshotState, string> = {
  recovered: "RECOVERED",
  cleared: "CLEARED",
  caution: "CAUTION",
  deload: "DELOAD",
  "autonomic-recovery-leading": "AUTONOMIC RECOVERY LEADING",
  "peripheral-strain": "PERIPHERAL STRAIN",
  "illness-risk": "ILLNESS RISK",
  "accumulating-fatigue": "ACCUMULATING FATIGUE",
  insufficient_data: "INSUFFICIENT DATA",
};

interface ColorBundle {
  text: string;
  ink: string;
  soft: string;
  tint: string;
  border: string;
  dot: string;
  ring: string;
  spark: string; // hex (for SVG/recharts)
  sparkFaded: string; // hex with low alpha (for gradient stop)
}

export const COLOR_TOKENS: Record<StateColor, ColorBundle> = {
  green: {
    text: "text-state-green",
    ink: "text-state-green-ink",
    soft: "bg-state-green-soft",
    tint: "bg-state-green-tint",
    border: "border-state-green",
    dot: "bg-state-green",
    ring: "ring-state-green",
    spark: "#10b981",
    sparkFaded: "rgba(16, 185, 129, 0.55)",
  },
  amber: {
    text: "text-state-amber",
    ink: "text-state-amber-ink",
    soft: "bg-state-amber-soft",
    tint: "bg-state-amber-tint",
    border: "border-state-amber",
    dot: "bg-state-amber",
    ring: "ring-state-amber",
    spark: "#f59e0b",
    sparkFaded: "rgba(245, 158, 11, 0.55)",
  },
  red: {
    text: "text-state-red",
    ink: "text-state-red-ink",
    soft: "bg-state-red-soft",
    tint: "bg-state-red-tint",
    border: "border-state-red",
    dot: "bg-state-red",
    ring: "ring-state-red",
    spark: "#ef4444",
    sparkFaded: "rgba(239, 68, 68, 0.55)",
  },
  blue: {
    text: "text-state-blue",
    ink: "text-state-blue-ink",
    soft: "bg-state-blue-soft",
    tint: "bg-state-blue-tint",
    border: "border-state-blue",
    dot: "bg-state-blue",
    ring: "ring-state-blue",
    spark: "#0ea5e9",
    sparkFaded: "rgba(14, 165, 233, 0.55)",
  },
  purple: {
    text: "text-state-purple",
    ink: "text-state-purple-ink",
    soft: "bg-state-purple-soft",
    tint: "bg-state-purple-tint",
    border: "border-state-purple",
    dot: "bg-state-purple",
    ring: "ring-state-purple",
    spark: "#8b5cf6",
    sparkFaded: "rgba(139, 92, 246, 0.55)",
  },
  rose: {
    text: "text-state-rose",
    ink: "text-state-rose-ink",
    soft: "bg-state-rose-soft",
    tint: "bg-state-rose-tint",
    border: "border-state-rose",
    dot: "bg-state-rose",
    ring: "ring-state-rose",
    spark: "#f43f5e",
    sparkFaded: "rgba(244, 63, 94, 0.55)",
  },
};

export const FLAGSHIP_TIER_TO_COLOR = {
  green: "green",
  caution: "amber",
  deload: "red",
  unknown: "amber",
  irregular: "amber",
  moderate: "amber",
  high: "green",
  adapted: "green",
  drift: "amber",
  fraying: "red",
} as const;
