import type { SchemeSource } from '@/types/scheme';
import { primarySourceIndex } from '@/lib/citations';
import { safeHref } from '@/lib/url';
import { SchemeBadges } from './SchemeBadges';

interface CitationFootnotesProps {
  sources: readonly SchemeSource[];
}

export function CitationFootnotes({ sources }: CitationFootnotesProps) {
  if (!sources.length) return null;
  const primaryIdx = primarySourceIndex(sources);
  return (
    <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
      <p className="eyebrow mb-1">Sources</p>
      <p className="mb-3 text-xs text-[var(--color-ink-subtle)]">
        From official government portals (MyScheme catalogue).
      </p>
      <ol className="flex flex-col gap-2" aria-label="Source references">
        {sources.map((s, idx) => {
          const num = idx + 1;
          const isPrimary = idx === primaryIdx;
          const sourceHref = safeHref(s.source);
          return (
            <li
              key={num}
              id={`src-footnote-${num}`}
              className={
                isPrimary
                  ? 'rounded-xl bg-[var(--color-peach-faint)] p-3 text-sm'
                  : 'text-sm text-[var(--color-ink-muted)]'
              }
            >
              {isPrimary ? (
                <div className="flex flex-col gap-1">
                  <span className="font-semibold text-[var(--color-ink)]">
                    [{num}] {s.scheme} — Official source
                  </span>
                  {sourceHref && (
                    <a
                      href={sourceHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[var(--color-saffron)] hover:underline"
                    >
                      MyScheme.gov.in / catalogue ↗
                    </a>
                  )}
                  <SchemeBadges source={s} />
                </div>
              ) : (
                <div className="flex flex-col">
                  <span>
                    <span className="font-medium text-[var(--color-ink)]">
                      [{num}] {s.scheme}
                    </span>{' '}
                    —{' '}
                    {sourceHref ? (
                      <a
                        href={sourceHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-[var(--color-saffron)] hover:underline"
                      >
                        MyScheme / catalogue
                      </a>
                    ) : (
                      'Retrieved context'
                    )}
                  </span>
                  <SchemeBadges source={s} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
