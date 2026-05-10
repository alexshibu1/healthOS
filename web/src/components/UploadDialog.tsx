import { type ChangeEvent, useEffect, useState } from "react";
import extractionPrompt from "../data/extraction_prompt.txt?raw";

type Step = 1 | 2 | 3;

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiBase: string;
  /** Skip the CSV flow and load the committed demo dashboard snapshot. */
  onSkipDemo?: () => void;
}

export function UploadDialog({
  open,
  onOpenChange,
  apiBase,
  onSkipDemo,
}: UploadDialogProps) {
  const [step, setStep] = useState<Step>(1);
  const [copyDone, setCopyDone] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileLabel, setFileLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setStep(1);
      setCopyDone(false);
      setUploading(false);
      setError(null);
      setFileLabel(null);
    }
  }, [open]);

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(extractionPrompt.trim());
      setCopyDone(true);
      setTimeout(() => setCopyDone(false), 2000);
    } catch {
      setError("Could not copy — select the preview text manually.");
    }
  }

  async function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setFileLabel(file.name);
    setUploading(true);

    const fd = new FormData();
    fd.append("file", file);

    try {
      const res = await fetch(`${apiBase}/upload`, {
        method: "POST",
        body: fd,
      });
      const body = (await res.json()) as { status?: string; error?: string };
      if (!res.ok || body.error) {
        setError(body.error ?? `Upload failed (${res.status})`);
        setUploading(false);
        return;
      }
      if (body.status === "ok") {
        window.location.reload();
        return;
      }
      setError("Unexpected response from server.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Network error — is the API running on port 8787?",
      );
    } finally {
      setUploading(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/25 p-4 backdrop-blur-[2px]"
      role="presentation"
      onClick={() => onOpenChange(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-dialog-title"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto border border-paper-divider bg-paper-tinted shadow-[0_24px_48px_-12px_rgba(22,20,15,0.18)]"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="border-b border-paper-divider px-6 py-5">
          <p
            id="upload-dialog-title"
            className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-subtle"
          >
            Get started
          </p>
          <div className="mt-3 flex items-center gap-2 font-mono text-[11px] tabular text-ink-muted">
            {([1, 2, 3] as const).map((n) => (
              <span key={n} className="flex items-center gap-2">
                <span
                  className={
                    step === n
                      ? "font-semibold text-ink"
                      : step > n
                        ? "text-ink-muted"
                        : "text-ink-faint"
                  }
                >
                  {n}
                </span>
                {n < 3 && <span className="text-ink-faint">—</span>}
              </span>
            ))}
          </div>
        </div>

        <div className="space-y-6 px-6 py-8">
          {step === 1 && (
            <>
              <h2 className="display text-chapter font-medium text-ink">
                Gather your data
              </h2>
              <p className="text-sm leading-relaxed text-ink-muted">
                Collect everything you have — screenshots from health apps, blood work PDFs,
                fitness app exports, notes. You don&apos;t need to organize it.
              </p>
              <p className="text-sm leading-relaxed text-ink-muted">
                Works with: Apple Health, Garmin, WHOOP, Oura, Strava, blood panels, anything
                you can screenshot or export.
              </p>
              <button
                type="button"
                onClick={() => setStep(2)}
                className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink underline decoration-paper-divider underline-offset-4 hover:text-ink-muted"
              >
                Got it, next →
              </button>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="display text-chapter font-medium text-ink">
                Ask an LLM to structure it
              </h2>
              <p className="text-sm leading-relaxed text-ink-muted">
                Open Claude, ChatGPT, or any LLM. Share your health data — paste screenshots,
                text, whatever you have. Then copy and paste this prompt:
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void copyPrompt()}
                  className="border border-ink bg-ink px-4 py-2.5 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-paper"
                >
                  {copyDone ? "Copied" : "Copy prompt"}
                </button>
              </div>
              <pre className="max-h-[200px] overflow-auto border border-paper-divider bg-paper/80 p-3 font-mono text-[10px] leading-relaxed text-ink-muted">
                {extractionPrompt.trim()}
              </pre>
              <p className="text-sm text-ink-muted">
                The LLM will return a CSV. Download it.
              </p>
              <button
                type="button"
                onClick={() => setStep(3)}
                className="inline-flex w-full items-center justify-center border border-ink bg-ink px-5 py-3 font-mono text-[11px] font-semibold uppercase tracking-[0.2em] text-paper shadow-sm transition hover:bg-ink/90 sm:w-auto"
              >
                I have the CSV →
              </button>
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="display text-chapter font-medium text-ink">
                Upload your CSV
              </h2>
              <p className="text-sm leading-relaxed text-ink-muted">
                Upload the CSV your LLM generated. We&apos;ll analyze it and show your
                personalized health dashboard.
              </p>
              <label className="block">
                <span className="sr-only">Choose CSV file</span>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="block w-full border border-paper-divider bg-paper px-3 py-2 font-mono text-[11px] file:mr-4 file:border-0 file:bg-transparent file:font-mono file:text-[11px] file:uppercase file:tracking-[0.18em]"
                  disabled={uploading}
                  onChange={(e) => void onFileChange(e)}
                />
              </label>
              {fileLabel && (
                <p className="font-mono text-[11px] text-ink-muted">
                  {fileLabel}
                  {uploading && (
                    <span className="ml-2 inline-flex items-center gap-2">
                      <span
                        className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-ink-muted border-t-transparent"
                        aria-hidden
                      />
                      Analyzing…
                    </span>
                  )}
                </p>
              )}
              {error && (
                <p className="border border-state-rose/40 bg-state-rose-soft px-3 py-2 font-mono text-[11px] text-state-rose-ink">
                  {error}
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-paper-divider px-6 py-4">
          {onSkipDemo ? (
            <button
              type="button"
              onClick={() => {
                onSkipDemo();
                onOpenChange(false);
              }}
              className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-muted underline decoration-paper-divider underline-offset-4 hover:text-ink"
            >
              Skip — view demo dashboard
            </button>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-subtle hover:text-ink"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
