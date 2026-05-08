import { useId, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { COLOR_TOKENS } from "../lib/stateColors";
import type { StateColor, ThresholdBand } from "../types";

export type MetricPrimerVariant = "card" | "hero" | "inline";

export interface MetricPrimerProps {
  label: string;
  value?: string | number;
  tier?: { state: StateColor; label: string };
  meaning: string;
  thresholdContext?: string;
  formula?: string;
  thresholdBands?: ThresholdBand[];
  mechanism: string;
  skillRef: string;
  dataAge?: string;
  sparkline?: number[];
  action?: string;
  variant?: MetricPrimerVariant;
  className?: string;
}

const EXPAND_TRANSITION = {
  duration: 0.22,
  ease: [0.32, 0.72, 0, 1] as [number, number, number, number],
};

export function MetricPrimer({
  label,
  value,
  tier,
  meaning,
  thresholdContext,
  formula,
  thresholdBands,
  mechanism,
  skillRef,
  dataAge,
  sparkline,
  action,
  variant = "card",
  className = "",
}: MetricPrimerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanderId = useId();
  const tierTokens = tier ? COLOR_TOKENS[tier.state] : null;

  const toggleExpanded = () => setIsExpanded((v) => !v);

  return (
    <div
      className={`group relative ${
        variant === "card"
          ? "rounded-xl border border-paper-divider bg-paper p-5 transition-shadow hover:shadow-sm"
          : variant === "hero"
            ? "rounded-2xl border border-paper-divider bg-paper p-8"
            : "border-l-2 border-paper-divider pl-4"
      } ${className}`}
    >
      {variant === "card" && (
        <CardGlance
          label={label}
          value={value}
          tier={tier}
          tierTokens={tierTokens}
          meaning={meaning}
          thresholdContext={thresholdContext}
          dataAge={dataAge}
          sparkline={sparkline}
          isExpanded={isExpanded}
          onToggle={toggleExpanded}
          expanderId={expanderId}
        />
      )}

      {variant === "hero" && (
        <HeroGlance
          label={label}
          value={value}
          tier={tier}
          tierTokens={tierTokens}
          meaning={meaning}
          action={action}
          isExpanded={isExpanded}
          onToggle={toggleExpanded}
          expanderId={expanderId}
        />
      )}

      {variant === "inline" && (
        <InlineGlance
          label={label}
          meaning={meaning}
          isExpanded={isExpanded}
          onToggle={toggleExpanded}
          expanderId={expanderId}
        />
      )}

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            id={expanderId}
            key="expander"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={EXPAND_TRANSITION}
            className="overflow-hidden"
          >
            <ExpanderBody
              formula={formula}
              thresholdBands={thresholdBands}
              mechanism={mechanism}
              skillRef={skillRef}
              variant={variant}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface GlanceCommonProps {
  label: string;
  meaning: string;
  isExpanded: boolean;
  onToggle: () => void;
  expanderId: string;
}

interface CardGlanceProps extends GlanceCommonProps {
  value?: string | number;
  tier?: { state: StateColor; label: string };
  tierTokens: ReturnType<() => (typeof COLOR_TOKENS)[StateColor]> | null;
  thresholdContext?: string;
  dataAge?: string;
  sparkline?: number[];
}

function CardGlance({
  label,
  value,
  tier,
  tierTokens,
  meaning,
  thresholdContext,
  dataAge,
  sparkline,
  isExpanded,
  onToggle,
  expanderId,
}: CardGlanceProps) {
  return (
    <>
      <div className="flex items-start justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-medium uppercase tracking-wider text-ink-muted">
            {label}
          </span>
          <ExpandButton
            isExpanded={isExpanded}
            onToggle={onToggle}
            expanderId={expanderId}
            label={label}
          />
        </div>
        {tier && tierTokens && (
          <span
            className={`inline-flex items-center gap-1.5 rounded-md ${tierTokens.soft} px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${tierTokens.ink}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tierTokens.dot}`} />
            {tier.label}
          </span>
        )}
      </div>

      {value !== undefined && (
        <div className="mt-4 tabular text-score font-semibold text-ink">
          {value}
        </div>
      )}

      {thresholdContext && (
        <div
          className={`mt-1 text-sm transition-colors ${
            tierTokens
              ? `text-ink-muted group-hover:${tierTokens.ink} group-focus-within:${tierTokens.ink}`
              : "text-ink-muted"
          }`}
        >
          {thresholdContext}
        </div>
      )}

      <div className="mt-4 text-sm leading-snug text-ink-muted transition-colors group-hover:text-ink group-focus-within:text-ink">
        {meaning}
      </div>

      {sparkline && sparkline.length > 0 && tierTokens && (
        <div className="mt-4 h-10">
          <Sparkline data={sparkline} color={tierTokens.spark} />
        </div>
      )}

      {dataAge && (
        <div className="mt-3 text-xs text-ink-subtle">{dataAge}</div>
      )}
    </>
  );
}

interface HeroGlanceProps extends GlanceCommonProps {
  value?: string | number;
  tier?: { state: StateColor; label: string };
  tierTokens: ReturnType<() => (typeof COLOR_TOKENS)[StateColor]> | null;
  action?: string;
}

function HeroGlance({
  label,
  value,
  tier,
  tierTokens,
  meaning,
  action,
  isExpanded,
  onToggle,
  expanderId,
}: HeroGlanceProps) {
  return (
    <>
      <div className="flex items-center gap-3">
        {tierTokens && (
          <span
            className={`inline-flex items-center gap-2 rounded-full ${tierTokens.soft} px-3 py-1 text-xs font-semibold uppercase tracking-wider ${tierTokens.ink}`}
          >
            <span className={`h-2 w-2 rounded-full ${tierTokens.dot}`} />
            {tier?.label ?? label}
          </span>
        )}
        <ExpandButton
          isExpanded={isExpanded}
          onToggle={onToggle}
          expanderId={expanderId}
          label={label}
        />
      </div>

      {value !== undefined && (
        <div className="mt-6 flex items-baseline gap-2">
          <span className="tabular text-hero font-bold text-ink">{value}</span>
          <span className="text-base text-ink-subtle">/ 100</span>
        </div>
      )}

      <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink-muted transition-colors group-hover:text-ink group-focus-within:text-ink">
        {meaning}
      </p>

      {action && (
        <div className="mt-6 flex items-center gap-2 text-sm font-medium text-ink">
          <span aria-hidden>→</span>
          <span>{action}</span>
        </div>
      )}
    </>
  );
}

interface InlineGlanceProps extends GlanceCommonProps {}

function InlineGlance({
  label,
  meaning,
  isExpanded,
  onToggle,
  expanderId,
}: InlineGlanceProps) {
  return (
    <div className="flex items-start gap-2">
      <ExpandButton
        isExpanded={isExpanded}
        onToggle={onToggle}
        expanderId={expanderId}
        label={label}
      />
      <span className="text-sm text-ink-muted transition-colors group-hover:text-ink group-focus-within:text-ink">
        {meaning}
      </span>
    </div>
  );
}

interface ExpandButtonProps {
  isExpanded: boolean;
  onToggle: () => void;
  expanderId: string;
  label: string;
}

function ExpandButton({
  isExpanded,
  onToggle,
  expanderId,
  label,
}: ExpandButtonProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
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
  );
}

interface ExpanderBodyProps {
  formula?: string;
  thresholdBands?: ThresholdBand[];
  mechanism: string;
  skillRef: string;
  variant: MetricPrimerVariant;
}

function ExpanderBody({
  formula,
  thresholdBands,
  mechanism,
  skillRef,
  variant,
}: ExpanderBodyProps) {
  return (
    <div
      className={`mt-5 border-t border-paper-divider pt-5 ${
        variant === "inline" ? "ml-7" : ""
      }`}
    >
      {formula && (
        <ExpanderSection title="How it's computed">
          <p className="text-sm leading-relaxed text-ink-muted">{formula}</p>
        </ExpanderSection>
      )}

      {thresholdBands && thresholdBands.length > 0 && (
        <ExpanderSection title="Threshold bands">
          <ul className="space-y-1.5 text-sm text-ink-muted">
            {thresholdBands.map((band) => {
              const tokens = COLOR_TOKENS[band.color];
              return (
                <li key={band.range} className="flex items-center gap-3">
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full ${tokens.dot}`}
                  />
                  <span className="tabular w-20 text-xs text-ink-subtle">
                    {band.range}
                  </span>
                  <span>{band.label}</span>
                </li>
              );
            })}
          </ul>
        </ExpanderSection>
      )}

      <ExpanderSection title="Why it matters">
        <p className="text-sm leading-relaxed text-ink-muted">{mechanism}</p>
      </ExpanderSection>

      <div className="mt-4 text-xs text-ink-subtle">
        <span className="font-mono">skill {skillRef}</span>
      </div>
    </div>
  );
}

function ExpanderSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-ink-subtle">
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
      <LineChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
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
