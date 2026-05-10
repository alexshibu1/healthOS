interface LandingProps {
  onOpenUpload: () => void;
  /** Skip CSV upload and show the committed demo fixture dashboard. */
  onUseDemo: () => void;
}

export function Landing({ onOpenUpload, onUseDemo }: LandingProps) {
  return (
    <div className="min-h-screen text-ink">
      <main className="mx-auto max-w-[600px] px-8 pb-24 pt-16">
        <div className="border-b border-paper-divider pb-8">
          <span className="display text-lg font-medium tracking-tight text-ink">
            health
            <span className="display font-light text-ink-muted">OS</span>
          </span>
        </div>

        <p className="mt-10 text-[1.05rem] leading-relaxed text-ink-muted">
          Personal health intelligence layer — ingests messy multi-source health data
          (Zepp/Amazfit, JeFit, Strava, blood panels) and produces monthly reports with a
          composite readiness score, bio-age proxy, and ranked top-3 interventions.
        </p>

        <button
          type="button"
          onClick={onOpenUpload}
          className="mt-12 inline-flex w-full items-center justify-center border border-ink bg-ink px-6 py-3.5 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-paper shadow-sm transition hover:bg-ink/90"
        >
          Analyze my health data
        </button>

        <button
          type="button"
          onClick={onUseDemo}
          className="mt-6 w-full text-center font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-muted underline decoration-paper-divider underline-offset-4 transition hover:text-ink"
        >
          View demo dashboard (skip upload)
        </button>
      </main>
    </div>
  );
}
