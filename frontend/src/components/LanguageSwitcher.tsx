import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { LANGUAGES, LANGUAGE_BY_CODE } from '@/i18n/languages';
import { useAppStore } from '@/store/appStore';
import { cn } from '@/lib/cn';

export function LanguageSwitcher() {
  const selected = useAppStore((s) => s.selectedLanguage);
  const setLanguage = useAppStore((s) => s.setLanguage);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const current = LANGUAGE_BY_CODE[selected] ?? LANGUAGES[0]!;

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Change language"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm font-medium transition-colors hover:border-[var(--color-ink)]"
      >
        <span className="text-base">🇮🇳</span>
        <span>{current.nativeLabel}</span>
        <ChevronDown size={14} strokeWidth={2} className={cn('transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label="Available languages"
          className="absolute top-full z-50 mt-2 flex min-w-[200px] flex-col gap-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-2 shadow-lg"
        >
          {LANGUAGES.map((l) => {
            const active = l.code === selected;
            return (
              <li key={l.code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => {
                    setLanguage(l.code);
                    setOpen(false);
                  }}
                  className={cn(
                    'flex w-full items-center justify-between gap-4 rounded-xl px-3 py-2 text-left text-sm transition-colors',
                    active
                      ? 'bg-[var(--color-peach-faint)] text-[var(--color-ink)]'
                      : 'hover:bg-[var(--color-surface)]',
                  )}
                >
                  <span className="flex flex-col">
                    <span className="font-medium">{l.nativeLabel}</span>
                    <span className="text-xs text-[var(--color-ink-subtle)]">{l.englishLabel}</span>
                  </span>
                  {active && <Check size={14} strokeWidth={2} className="text-[var(--color-saffron)]" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
