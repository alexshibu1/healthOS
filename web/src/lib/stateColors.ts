import type { SnapshotState, StateColor } from "../types";

export const STATE_TO_COLOR: Record<SnapshotState, StateColor> = {
  recovered: "green",
  cleared: "green",
  caution: "amber",
  deload: "red",
  "autonomic-recovery-leading": "blue",
  "peripheral-strain": "purple",
  "illness-risk": "rose",
};

export const STATE_LABEL: Record<SnapshotState, string> = {
  recovered: "RECOVERED",
  cleared: "CLEARED",
  caution: "CAUTION",
  deload: "DELOAD",
  "autonomic-recovery-leading": "AUTONOMIC RECOVERY LEADING",
  "peripheral-strain": "PERIPHERAL STRAIN",
  "illness-risk": "ILLNESS RISK",
};

interface ColorBundle {
  text: string;
  ink: string;
  soft: string;
  tint: string;
  border: string;
  dot: string;
  ring: string;
  spark: string;
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
    spark: "#16a34a",
  },
  amber: {
    text: "text-state-amber",
    ink: "text-state-amber-ink",
    soft: "bg-state-amber-soft",
    tint: "bg-state-amber-tint",
    border: "border-state-amber",
    dot: "bg-state-amber",
    ring: "ring-state-amber",
    spark: "#d97706",
  },
  red: {
    text: "text-state-red",
    ink: "text-state-red-ink",
    soft: "bg-state-red-soft",
    tint: "bg-state-red-tint",
    border: "border-state-red",
    dot: "bg-state-red",
    ring: "ring-state-red",
    spark: "#dc2626",
  },
  blue: {
    text: "text-state-blue",
    ink: "text-state-blue-ink",
    soft: "bg-state-blue-soft",
    tint: "bg-state-blue-tint",
    border: "border-state-blue",
    dot: "bg-state-blue",
    ring: "ring-state-blue",
    spark: "#2563eb",
  },
  purple: {
    text: "text-state-purple",
    ink: "text-state-purple-ink",
    soft: "bg-state-purple-soft",
    tint: "bg-state-purple-tint",
    border: "border-state-purple",
    dot: "bg-state-purple",
    ring: "ring-state-purple",
    spark: "#7c3aed",
  },
  rose: {
    text: "text-state-rose",
    ink: "text-state-rose-ink",
    soft: "bg-state-rose-soft",
    tint: "bg-state-rose-tint",
    border: "border-state-rose",
    dot: "bg-state-rose",
    ring: "ring-state-rose",
    spark: "#e11d48",
  },
};

export const FLAGSHIP_TIER_TO_COLOR = {
  green: "green",
  caution: "amber",
  deload: "red",
  irregular: "amber",
  moderate: "amber",
  high: "green",
  adapted: "green",
  drift: "amber",
  fraying: "red",
} as const;
