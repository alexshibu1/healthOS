import { useCallback, useId, useRef, useState } from "react";
import { SectionDivider } from "./SectionDivider";

interface LLMHandoffProps {
  promptText: string;
  /** Roman numeral — IV when divergence chapter is hidden, V when shown. */
  numeral: string;
}

/**
 * Chapter V — copy a deterministic prompt for external LLM recommendations.
 * Clipboard first; textarea fallback for contexts where the API is blocked.
 */
export function LLMHandoff({ promptText, numeral }: LLMHandoffProps) {
  const [copied, setCopied] = useState(false);
  /** Open by default — the prompt is the product; hiding it hurt usability. */
  const [previewOpen, setPreviewOpen] = useState(true);
  const [copyError, setCopyError] = useState<string | null>(null);
  const fallbackRef = useRef<HTMLTextAreaElement>(null);
  const previewId = useId();

  const runFallbackCopy = useCallback(() => {
    const el = fallbackRef.current;
    if (!el) return false;
    el.style.display = "block";
    el.select();
    el.setSelectionRange(0, promptText.length);
    try {
      const ok = document.execCommand("copy");
      el.style.display = "none";
      return ok;
    } catch {
      el.style.display = "none";
      return false;
    }
  }, [promptText.length]);

  const handleCopy = useCallback(async () => {
    setCopyError(null);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(promptText);
      } else if (!runFallbackCopy()) {
        setCopyError("Copy blocked — select the preview text manually.");
        return;
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      if (!runFallbackCopy()) {
        setCopyError("Could not copy. Try expanding the preview and copy manually.");
        return;
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    }
  }, [promptText, runFallbackCopy]);

  return (
    <>
      <SectionDivider numeral={numeral} title="GET YOUR RECOMMENDATIONS" />
      <section className="mx-auto max-w-6xl px-8 pb-12">
        <p className="display max-w-3xl text-lg font-light leading-relaxed text-ink">
          The charts above are facts from your exports. For ranked, personalized
          next steps, copy the structured prompt — it bundles profile, today&apos;s
          composite, three lenses, divergence, and output rules so any assistant can
          respond at full fidelity (Claude, ChatGPT, Gemini, etc.).
        </p>
        <p className="mt-4 font-mono text-xs leading-relaxed text-ink-muted">
          {promptText.length.toLocaleString()} characters · ready to paste · preview
          scrolls if long
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={() => void handleCopy()}
            aria-live="polite"
            className="inline-flex w-fit min-h-[44px] items-center rounded-sm bg-ink px-6 py-3 text-sm font-medium text-paper shadow-card transition-[opacity,transform] hover:opacity-90 active:scale-[0.99]"
          >
            {copied ? "Copied to clipboard" : "Copy full prompt"}
          </button>
          {copyError && (
            <span className="font-mono text-xs text-state-red-ink">{copyError}</span>
          )}
        </div>
        <p className="mt-3 max-w-2xl font-mono text-[11px] uppercase tracking-wide text-ink-subtle">
          Nothing is uploaded — text stays in your browser until you paste elsewhere.
        </p>

        <textarea
          ref={fallbackRef}
          readOnly
          aria-hidden
          defaultValue={promptText}
          className="pointer-events-none fixed -left-[9999px] top-0 h-px w-px opacity-0"
          tabIndex={-1}
        />

        <div className="mt-10 border-t border-paper-divider pt-8">
          <button
            type="button"
            id={previewId}
            aria-expanded={previewOpen}
            onClick={() => setPreviewOpen((o) => !o)}
            className="font-mono text-xs uppercase tracking-[0.22em] text-ink-muted transition-colors hover:text-ink"
          >
            {previewOpen ? "Hide prompt preview" : "Show prompt preview"}
          </button>
          {previewOpen && (
            <pre
              className="font-mono mt-5 max-h-[min(32rem,62vh)] max-w-4xl overflow-auto rounded-md border border-paper-divider bg-paper-elevated p-6 text-[13px] leading-[1.65] text-ink shadow-card"
              tabIndex={0}
            >
              {promptText}
            </pre>
          )}
        </div>
      </section>
    </>
  );
}
