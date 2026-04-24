import { Mic, SearchIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

export type Mode = 'talk' | 'finder';

interface ModeTabsProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeTabs({ mode, onChange }: ModeTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Interaction mode"
      className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-1 shadow-sm"
    >
      <TabButton active={mode === 'talk'} onClick={() => onChange('talk')} icon={<Mic size={14} strokeWidth={2} />}>
        Talk
      </TabButton>
      <TabButton active={mode === 'finder'} onClick={() => onChange('finder')} icon={<SearchIcon size={14} strokeWidth={2} />}>
        Find schemes
      </TabButton>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
        active
          ? 'bg-[var(--color-cta)] text-[var(--color-cta-ink)]'
          : 'text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]',
      )}
    >
      {icon}
      {children}
    </button>
  );
}
