interface ExplainPanelProps {
  text: string | null | undefined;
}

export function ExplainPanel({ text }: ExplainPanelProps) {
  if (!text || !text.trim()) return null;
  return (
    <section className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <p className="eyebrow mb-1">How this answer was chosen</p>
      <p className="text-sm text-[var(--color-ink)]">{text.trim()}</p>
    </section>
  );
}
