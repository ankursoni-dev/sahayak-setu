import { memo } from 'react';
import { ExternalLink } from 'lucide-react';
import type { CuratedScheme } from '@/data/curatedSchemes';
import { safeHref } from '@/lib/url';

interface SchemeCardProps {
  scheme: CuratedScheme;
  onOpen: (scheme: CuratedScheme) => void;
  onCheckEligibility: (scheme: CuratedScheme) => void;
}

function SchemeCardInner({ scheme, onOpen, onCheckEligibility }: SchemeCardProps) {
  const applyHref = safeHref(scheme.applyLink);
  const sourceHref = safeHref(scheme.sourceLink);
  return (
    <article className="flex h-full flex-col gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 transition-all hover:-translate-y-0.5 hover:shadow-md">
      <button
        type="button"
        onClick={() => onOpen(scheme)}
        className="flex flex-1 flex-col items-start gap-2 text-left"
        aria-label={`View details for ${scheme.name}`}
      >
        <span className="text-2xl" aria-hidden="true">
          {scheme.emoji}
        </span>
        <h3 className="text-lg">{scheme.name}</h3>
        <p className="text-sm text-[var(--color-ink-muted)]">{scheme.summary}</p>
      </button>
      <div className="mt-auto flex flex-wrap items-center gap-2">
        {applyHref && (
          <a
            href={applyHref}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Apply now for ${scheme.name}`}
            className="inline-flex items-center gap-1 rounded-full bg-[var(--color-cta)] px-3 py-1.5 text-xs font-medium text-[var(--color-cta-ink)]"
          >
            Apply <ExternalLink size={11} strokeWidth={2.5} />
          </a>
        )}
        {sourceHref && (
          <a
            href={sourceHref}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Official information for ${scheme.name}`}
            className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border-strong)] px-3 py-1.5 text-xs font-medium"
          >
            Info <ExternalLink size={11} strokeWidth={2.5} />
          </a>
        )}
        <button
          type="button"
          onClick={() => onCheckEligibility(scheme)}
          className="ml-auto text-xs font-medium text-[var(--color-saffron)] hover:underline"
        >
          Check eligibility →
        </button>
      </div>
    </article>
  );
}

export const SchemeCard = memo(SchemeCardInner);
