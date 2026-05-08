interface SectionDividerProps {
  /** Roman numeral for the chapter, e.g. "I", "II", "III". */
  numeral: string;
  /** Editorial heading for the section, e.g. "Today's Read". */
  title: string;
  /** Optional inline annotation, set in mono. */
  annotation?: string;
}

/**
 * Editorial chapter heading — the unifying rhythm element across the page.
 *
 * Renders as a Roman numeral + serif title, separated from the body by a
 * single full-width hairline. Visual differentiation comes from font weight
 * (Newsreader 300 light) — italic is intentionally avoided per design rule.
 * Inspired by clinical-paper / journal tables of contents (NEJM, The
 * Lancet) so the page reads as a numbered volume, not a dashboard.
 */
export function SectionDivider({
  numeral,
  title,
  annotation,
}: SectionDividerProps) {
  return (
    <div className="mx-auto max-w-6xl px-8 pt-12 pb-4">
      <div className="flex items-baseline gap-4 border-b border-paper-divider pb-3">
        <span className="display tabular text-xs font-medium uppercase tracking-[0.32em] text-ink-faint">
          {numeral}
        </span>
        <h2 className="display flex-1 text-chapter font-light tracking-tight text-ink">
          {title}
        </h2>
        {annotation && (
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-subtle">
            {annotation}
          </span>
        )}
      </div>
    </div>
  );
}
