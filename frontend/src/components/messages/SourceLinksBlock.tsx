import { ExternalLink } from 'lucide-react';
import type { SchemeSource } from '@/types/scheme';
import { safeHref } from '@/lib/url';
import { SchemeBadges } from './SchemeBadges';

interface SourceLinksBlockProps {
  sources: readonly SchemeSource[];
  heading: string;
}

function confidenceEmoji(label?: string): string {
  if (!label) return '';
  if (/strong match/i.test(label) || /verified/i.test(label)) return '🟢';
  if (/moderate/i.test(label)) return '🟡';
  return '🟠';
}

export function SourceLinksBlock({ sources, heading }: SourceLinksBlockProps) {
  const rows = sources.filter((s) => s.apply_link || s.source);
  if (!rows.length) return null;

  return (
    <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
      <p className="eyebrow mb-3">{heading}</p>
      <ul className="flex flex-col gap-3">
        {rows.map((s, i) => {
          const isApply = s.cta_label === 'Apply Now';
          const applyHref = safeHref(s.apply_link);
          const sourceHref = safeHref(s.source);
          return (
            <li
              key={`${s.scheme}-${i}`}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--color-surface)] px-3 py-2"
            >
              <div className="flex flex-col">
                <span className="font-medium text-[var(--color-ink)]">{s.scheme}</span>
                {s.confidence_label && (
                  <span className="text-xs text-[var(--color-ink-muted)]">
                    {confidenceEmoji(s.confidence_label)} {s.confidence_label}
                  </span>
                )}
                <SchemeBadges source={s} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {applyHref && (
                  <a
                    href={applyHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-cta)] px-3 py-1.5 text-xs font-medium text-[var(--color-cta-ink)]"
                    aria-label={`${isApply ? 'Apply now' : 'Check eligibility'} for ${s.scheme}`}
                  >
                    {isApply ? 'Apply now' : 'Check eligibility'}
                    <ExternalLink size={12} strokeWidth={2} />
                  </a>
                )}
                {sourceHref && (
                  <a
                    href={sourceHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border-strong)] px-3 py-1.5 text-xs font-medium text-[var(--color-ink)]"
                    aria-label={`Official information for ${s.scheme}`}
                  >
                    Official info
                    <ExternalLink size={12} strokeWidth={2} />
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
