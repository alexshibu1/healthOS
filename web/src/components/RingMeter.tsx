import { useId, type ReactNode } from "react";
import { motion } from "framer-motion";
import { COLOR_TOKENS } from "../lib/stateColors";
import type { StateColor } from "../types";

export type RingSize = "xs" | "sm" | "md" | "lg";
export type RingVariant = "arc" | "orb";

export interface RingMeterProps {
  value: number; // 0-100 fill percentage; ignored when variant === 'orb'
  color: StateColor;
  size?: RingSize;
  variant?: RingVariant;
  glow?: boolean;
  /**
   * Threshold tick positions on the ring track, expressed as percentages
   * (0-100). Each tick renders as a small notched marker so you can read the
   * caution/deload boundaries without expanding the card.
   */
  thresholdTicks?: number[];
  children?: ReactNode;
}

const SIZE_TO_DIM: Record<
  RingSize,
  { dim: number; stroke: number; glowBlur: number }
> = {
  // glowBlur scales with ring size so a small ring doesn't drown in
  // drop-shadow halo. The previous 5px-everywhere setting was bloomy on
  // the sm rings used in the Signals row.
  xs: { dim: 48, stroke: 4, glowBlur: 2 },
  sm: { dim: 84, stroke: 6, glowBlur: 3 },
  md: { dim: 144, stroke: 9, glowBlur: 4 },
  lg: { dim: 184, stroke: 11, glowBlur: 6 },
};

export function RingMeter({
  value,
  color,
  size = "md",
  variant = "arc",
  glow = true,
  thresholdTicks,
  children,
}: RingMeterProps) {
  const id = useId();
  const { dim, stroke, glowBlur } = SIZE_TO_DIM[size];
  const tokens = COLOR_TOKENS[color];

  if (variant === "orb") {
    return (
      <div
        className="relative flex items-center justify-center"
        style={{ width: dim, height: dim }}
      >
        {/* outer halo */}
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background: `radial-gradient(circle at 50% 35%, ${tokens.spark}26 0%, ${tokens.spark}0d 50%, transparent 75%)`,
          }}
        />
        {/* inner orb gem — white-to-color gradient on light bg */}
        <div
          className="absolute inset-3 rounded-full"
          style={{
            background: `radial-gradient(circle at 50% 28%, #ffffff 0%, ${tokens.spark}1a 70%, ${tokens.spark}26 100%)`,
            border: `1.5px solid ${tokens.spark}80`,
            boxShadow: glow
              ? `inset 0 0 14px ${tokens.spark}1a, 0 4px 18px ${tokens.spark}1f`
              : undefined,
          }}
        />
        <div className="relative z-10 flex flex-col items-center justify-center">
          {children}
        </div>
      </div>
    );
  }

  const r = (dim - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, value));
  const dashOffset = circumference * (1 - clamped / 100);

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: dim, height: dim }}
    >
      <svg width={dim} height={dim} className="-rotate-90" aria-hidden>
        <defs>
          {/* Stroke gradient: vivid at the leading edge, softer at the start */}
          <linearGradient
            id={`ring-grad-${id}`}
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop offset="0%" stopColor={tokens.spark} stopOpacity="0.65" />
            <stop offset="100%" stopColor={tokens.spark} stopOpacity="1" />
          </linearGradient>
        </defs>

        {/* Track — slightly more contrast against cream background than before */}
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          stroke="rgba(22, 20, 15, 0.10)"
        />

        {/* Progress arc — animates in on mount. Drawn BEFORE the threshold
            ticks so the ticks sit on top, not under the colored arc. */}
        <motion.circle
          cx={dim / 2}
          cy={dim / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          stroke={`url(#ring-grad-${id})`}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 0.9, ease: [0.32, 0.72, 0, 1] }}
          strokeLinecap="round"
          style={
            glow
              ? { filter: `drop-shadow(0 0 ${glowBlur}px ${tokens.spark}80)` }
              : undefined
          }
        />

        {/* Threshold ticks — thin radial dashes sitting on top of track AND
            progress. Editorial tick-mark feel, not pinball lights. */}
        {thresholdTicks?.map((pct) => {
          const angle = (pct / 100) * 2 * Math.PI;
          const cosA = Math.cos(angle);
          const sinA = Math.sin(angle);
          const inner = r - stroke / 2 - 1;
          const outer = r + stroke / 2 + 1;
          return (
            <line
              key={pct}
              x1={dim / 2 + inner * cosA}
              y1={dim / 2 + inner * sinA}
              x2={dim / 2 + outer * cosA}
              y2={dim / 2 + outer * sinA}
              stroke="rgba(22, 20, 15, 0.45)"
              strokeWidth={1.25}
              strokeLinecap="round"
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {children}
      </div>
    </div>
  );
}
