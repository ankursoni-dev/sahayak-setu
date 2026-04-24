import { Fragment } from 'react';
import type { SchemeSource } from '@/types/scheme';
import { segmentWithCitations } from '@/lib/citations';

interface AnswerBodyProps {
  text: string;
  sources: readonly SchemeSource[];
}

function citationTitle(source: SchemeSource | undefined): string {
  if (!source) return '';
  const scheme = source.scheme || 'Scheme';
  const preview = (source.preview_text || '').trim();
  const line = preview ? `${scheme} — ${preview}` : `${scheme} — Official catalogue match`;
  return line.length > 280 ? `${line.slice(0, 278)}…` : line;
}

export function AnswerBody({ text, sources }: AnswerBodyProps) {
  if (!text) return <p className="text-[var(--color-ink-muted)]">No answer provided.</p>;
  if (!sources.length) {
    return <p className="whitespace-pre-wrap text-base leading-relaxed text-[var(--color-ink)]">{text}</p>;
  }
  const segments = segmentWithCitations(text, sources.length);
  return (
    <p className="whitespace-pre-wrap text-base leading-relaxed text-[var(--color-ink)]">
      {segments.map((seg, idx) =>
        seg.kind === 'text' ? (
          <Fragment key={idx}>{seg.value}</Fragment>
        ) : (
          <sup key={idx} className="ml-0.5">
            <a
              href={`#src-footnote-${seg.index}`}
              title={citationTitle(sources[seg.index - 1])}
              className="rounded px-1 text-xs text-[var(--color-saffron)] no-underline hover:bg-[var(--color-peach-faint)]"
            >
              [{seg.index}]
            </a>
          </sup>
        ),
      )}
    </p>
  );
}
