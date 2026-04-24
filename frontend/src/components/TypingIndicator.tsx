export function TypingIndicator() {
  return (
    <div
      className="flex items-center gap-1.5 rounded-full bg-[var(--color-surface)] px-4 py-3 w-fit"
      aria-live="polite"
      aria-label="Assistant is thinking"
    >
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-ink-subtle)]"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  );
}
