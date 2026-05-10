export function Disclaimer() {
  return (
    <footer className="mx-auto max-w-6xl px-8 pb-12 pt-16">
      <div className="border-t border-paper-divider pt-6">
        <div className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-subtle">
          Colophon
        </div>
        <p className="display mt-3 max-w-2xl text-xs font-light leading-relaxed text-ink-muted">
          healthOS is a personal-analysis tool, not a medical device. The
          bio-age proxy, readiness score, and flagship metrics are
          illustrative composites built from your own data — they are not
          diagnoses and not medical advice. Consult a clinician before
          changing training load, supplementation, or treatment based on
          anything you see here.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
          <span>healthOS</span>
          <span aria-hidden>·</span>
          <span>set in Newsreader, IBM Plex Mono, Inter</span>
        </div>
        <p className="mt-5 font-mono text-[11px] leading-relaxed text-ink-muted">
          Built with ❤️ by{" "}
          <a
            href="https://alexshibu.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-ink underline decoration-paper-divider underline-offset-4 transition-colors hover:text-ink-muted hover:decoration-ink-faint"
          >
            Alex Shibu
          </a>
        </p>
      </div>
    </footer>
  );
}
