import { StatusIndicator } from '@/components/StatusIndicator';

const NAV_ITEMS: { href: string; label: string }[] = [
  { href: '#features', label: 'Features' },
  { href: '#schemes', label: 'Schemes' },
  { href: '#conversation', label: 'Ask' },
];

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-bg)_85%,transparent)] backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-6">
        <a href="/" className="flex items-baseline gap-2 no-underline" aria-label="SahayakSetu home">
          <span className="font-display text-xl tracking-tight text-[var(--color-ink)]">sahayaksetu</span>
          <span className="hidden text-xs text-[var(--color-ink-subtle)] sm:inline">सहायक सेतु</span>
        </a>
        <nav aria-label="Primary" className="hidden items-center gap-8 md:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-xs font-medium uppercase tracking-[0.14em] text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <StatusIndicator />
        </div>
      </div>
    </header>
  );
}
