interface ModerationMessageProps {
  content: string;
  category: string | null | undefined;
}

export function ModerationMessage({ content, category }: ModerationMessageProps) {
  const headline =
    category === 'harmful'
      ? "We can't assist with that request."
      : category === 'off_topic'
        ? 'I help with government schemes and civic services.'
        : null;

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      {headline && <p className="mb-1 font-medium text-[var(--color-ink)]">{headline}</p>}
      <p className="text-sm text-[var(--color-ink-muted)]">
        <span aria-hidden="true">🙏 </span>
        {content}
      </p>
    </div>
  );
}
