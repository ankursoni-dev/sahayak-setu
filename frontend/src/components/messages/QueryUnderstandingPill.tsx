import type { QueryDebug } from '@/types/scheme';

interface QueryUnderstandingPillProps {
  queryDebug: QueryDebug | null | undefined;
}

export function QueryUnderstandingPill({ queryDebug }: QueryUnderstandingPillProps) {
  if (!queryDebug?.original || !queryDebug?.rewritten) return null;
  // Case-insensitive comparison — lowercasing alone isn't a meaningful rewrite.
  if (queryDebug.original.trim().toLowerCase() === queryDebug.rewritten.trim().toLowerCase()) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="rounded-full bg-[var(--color-surface)] px-2.5 py-0.5 text-[var(--color-ink-muted)]">
        {queryDebug.original}
      </span>
      <span aria-hidden="true" className="text-[var(--color-ink-subtle)]">
        →
      </span>
      <span className="rounded-full bg-[var(--color-peach-faint)] px-2.5 py-0.5 text-[var(--color-ink)]">
        {queryDebug.rewritten}
      </span>
    </div>
  );
}
