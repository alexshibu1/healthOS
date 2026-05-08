interface NavProps {
  date?: string;
}

export function Nav({ date }: NavProps) {
  const today =
    date ??
    new Date().toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    });

  return (
    <header className="border-b border-paper-divider bg-paper">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-4">
        <div className="flex items-baseline gap-3">
          <span className="text-base font-semibold tracking-tight text-ink">
            healthOS
          </span>
          <span className="text-xs uppercase tracking-widest text-ink-subtle">
            Daily Snapshot
          </span>
        </div>
        <span className="tabular text-sm text-ink-muted">{today}</span>
      </div>
    </header>
  );
}
