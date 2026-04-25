import { useEffect, useRef } from 'react';
import { X, ExternalLink } from 'lucide-react';
import type { CuratedScheme } from '@/data/curatedSchemes';
import { safeHref } from '@/lib/url';

interface SchemeSheetProps {
  scheme: CuratedScheme | null;
  onClose: () => void;
  onAskAboutThis: (scheme: CuratedScheme) => void;
}

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export function SchemeSheet({ scheme, onClose, onAskAboutThis }: SchemeSheetProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  // Element that opened the sheet — restore focus there on close so keyboard users
  // don't get dropped at <body> after dismissing.
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!scheme) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      // Trap Tab inside the dialog.
      if (e.key === 'Tab' && dialogRef.current) {
        const nodes = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
        if (!nodes.length) return;
        const first = nodes[0]!;
        const last = nodes[nodes.length - 1]!;
        const active = document.activeElement as HTMLElement | null;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Move focus into the dialog so screen readers announce it and Tab navigation
    // starts inside. Defer one frame so the close button is mounted.
    const focusTimer = window.setTimeout(() => {
      closeBtnRef.current?.focus();
    }, 0);

    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      window.clearTimeout(focusTimer);
      previousFocusRef.current?.focus?.();
    };
  }, [scheme, onClose]);

  if (!scheme) return null;

  const applyHref = safeHref(scheme.applyLink);
  const sourceHref = safeHref(scheme.sourceLink);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="scheme-sheet-title"
      ref={dialogRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div
        className="absolute inset-0 bg-[rgba(10,10,10,0.4)] backdrop-blur-sm"
        aria-hidden="true"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 shadow-lg">
        <button
          ref={closeBtnRef}
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
          {applyHref && (
            <a
              href={applyHref}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-cta)] px-4 py-2 text-sm font-medium text-[var(--color-cta-ink)]"
            >
              Apply now <ExternalLink size={12} strokeWidth={2.5} />
            </a>
          )}
          {sourceHref && (
            <a
              href={sourceHref}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border-strong)] px-4 py-2 text-sm font-medium"
            >
              Official info <ExternalLink size={12} strokeWidth={2.5} />
            </a>
          )}
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
