import { useEffect } from 'react';
import { X, ExternalLink } from 'lucide-react';
import type { CuratedScheme } from '@/data/curatedSchemes';

interface SchemeSheetProps {
  scheme: CuratedScheme | null;
  onClose: () => void;
  onAskAboutThis: (scheme: CuratedScheme) => void;
}

export function SchemeSheet({ scheme, onClose, onAskAboutThis }: SchemeSheetProps) {
  useEffect(() => {
    if (!scheme) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [scheme, onClose]);

  if (!scheme) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="scheme-sheet-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div
        className="absolute inset-0 bg-[rgba(10,10,10,0.4)] backdrop-blur-sm"
        aria-hidden="true"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 shadow-lg">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 inline-flex h-8 w-8 items-center justify-center rounded-full text-[var(--color-ink-muted)] hover:bg-[var(--color-surface)]"
        >
          <X size={16} strokeWidth={2} />
        </button>
        <p className="eyebrow mb-2">{scheme.ministry}</p>
        <h3 id="scheme-sheet-title" className="mb-4 text-2xl">
          <span aria-hidden="true" className="mr-2">
            {scheme.emoji}
          </span>
          {scheme.name}
        </h3>
        <dl className="mb-5 flex flex-col gap-3 text-sm">
          <div>
            <dt className="eyebrow">Key benefit</dt>
            <dd className="mt-0.5 text-[var(--color-ink)]">{scheme.benefit}</dd>
          </div>
          <div>
            <dt className="eyebrow">Eligibility</dt>
            <dd className="mt-0.5 text-[var(--color-ink)]">{scheme.eligibility}</dd>
          </div>
        </dl>
        <div className="mb-4 flex flex-wrap gap-2">
          <a
            href={scheme.applyLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-cta)] px-4 py-2 text-sm font-medium text-[var(--color-cta-ink)]"
          >
            Apply now <ExternalLink size={12} strokeWidth={2.5} />
          </a>
          <a
            href={scheme.sourceLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border-strong)] px-4 py-2 text-sm font-medium"
          >
            Official info <ExternalLink size={12} strokeWidth={2.5} />
          </a>
        </div>
        <button
          type="button"
          onClick={() => onAskAboutThis(scheme)}
          className="w-full btn-outline"
        >
          Ask about this →
        </button>
      </div>
    </div>
  );
}
