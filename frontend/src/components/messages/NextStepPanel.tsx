interface NextStepPanelProps {
  text: string | null | undefined;
}

export function NextStepPanel({ text }: NextStepPanelProps) {
  if (!text || !text.trim()) return null;
  return (
    <section className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-peach-faint)] p-4">
      <header className="mb-2 flex items-center justify-between">
        <span className="eyebrow">Next step</span>
        <span className="text-xs text-[var(--color-ink-muted)]">⏱ quick action</span>
      </header>
      <ol className="flex flex-col gap-2">
        <li className="flex items-start gap-3">
          <span className="mt-0.5 inline-flex h-6 w-6 flex-none items-center justify-center rounded-full bg-[var(--color-cta)] text-xs font-semibold text-[var(--color-cta-ink)]">
            1
          </span>
          <div>
            <p className="font-medium text-[var(--color-ink)]">{text.trim()}</p>
            <p className="text-xs text-[var(--color-ink-muted)]">Use official links below to continue safely.</p>
          </div>
        </li>
      </ol>
    </section>
  );
}
