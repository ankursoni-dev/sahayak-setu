import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { LANGUAGES, LANGUAGE_BY_CODE } from '@/i18n/languages';
import { useAppStore } from '@/store/appStore';
import { cn } from '@/lib/cn';

export function LanguageSwitcher() {
  const selected = useAppStore((s) => s.selectedLanguage);
  const setLanguage = useAppStore((s) => s.setLanguage);
  const [open, setOpen] = useState(false);
  // Index of the keyboard-focused option while the listbox is open. -1 means "none".
  // Mouse hover does NOT change this — only ArrowUp/Down/Home/End/Tab navigation does,
  // matching the WAI-ARIA listbox pattern.
  const [activeIdx, setActiveIdx] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const current = LANGUAGE_BY_CODE[selected] ?? LANGUAGES[0]!;

  useEffect(() => {
    if (!open) {
      setActiveIdx(-1);
      return;
    }
    const onDoc = (e: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  // Initialize the active index to the currently-selected option whenever the
  // listbox opens, so keyboard users land on a sensible starting point.
  useEffect(() => {
    if (!open) return;
    const idx = LANGUAGES.findIndex((l) => l.code === selected);
    setActiveIdx(idx >= 0 ? idx : 0);
  }, [open, selected]);

  // Move focus to the active option whenever the index changes — this is what
  // gives a screen reader the "Hindi (हिंदी), 2 of 6" announcement.
  useEffect(() => {
    if (!open || activeIdx < 0) return;
    optionRefs.current[activeIdx]?.focus();
  }, [open, activeIdx]);

  const choose = (idx: number) => {
    const lang = LANGUAGES[idx];
    if (!lang) return;
    setLanguage(lang.code);
    setOpen(false);
    // Restore focus to the trigger so Tab order continues from the dropdown's anchor.
    triggerRef.current?.focus();
  };

  const onTriggerKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setOpen(true);
    }
  };

  const onListKeyDown = (e: React.KeyboardEvent<HTMLUListElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
      return;
    }
    if (e.key === 'Tab') {
      // Don't trap Tab — close and let the browser move on.
      setOpen(false);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => (i + 1) % LANGUAGES.length);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => (i <= 0 ? LANGUAGES.length - 1 : i - 1));
      return;
    }
    if (e.key === 'Home') {
      e.preventDefault();
      setActiveIdx(0);
      return;
    }
    if (e.key === 'End') {
      e.preventDefault();
      setActiveIdx(LANGUAGES.length - 1);
      return;
    }
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (activeIdx >= 0) choose(activeIdx);
    }
  };

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Change language"
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onTriggerKeyDown}
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
          tabIndex={-1}
          onKeyDown={onListKeyDown}
          className="absolute top-full z-50 mt-2 flex min-w-[200px] flex-col gap-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-2 shadow-lg"
        >
          {LANGUAGES.map((l, idx) => {
            const active = l.code === selected;
            return (
              <li key={l.code}>
                <button
                  ref={(el) => {
                    optionRefs.current[idx] = el;
                  }}
                  type="button"
                  role="option"
                  aria-selected={active}
                  tabIndex={idx === activeIdx ? 0 : -1}
                  onClick={() => choose(idx)}
                  onMouseEnter={() => setActiveIdx(idx)}
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
