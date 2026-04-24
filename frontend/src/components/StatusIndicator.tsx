import { useAppStore } from '@/store/appStore';
import { cn } from '@/lib/cn';

const TONE_CLASS: Record<string, string> = {
  green: 'bg-[var(--color-success)]',
  orange: 'bg-[var(--color-saffron)]',
  red: 'bg-[var(--color-error)]',
  yellow: 'bg-[var(--color-warn)]',
  blue: 'bg-[var(--color-info)]',
};

export function StatusIndicator() {
  const text = useAppStore((s) => s.statusText);
  const tone = useAppStore((s) => s.statusTone);
  const pulse = text === 'Thinking...' || text === 'Listening...' || text === 'Speaking...';

  return (
    <div
      className="flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-xs text-[var(--color-ink-muted)]"
      aria-live="polite"
      aria-atomic="true"
    >
      <span
        className={cn(
          'inline-block h-1.5 w-1.5 rounded-full',
          TONE_CLASS[tone] ?? TONE_CLASS.green,
          pulse && 'animate-pulse',
        )}
      />
      <span>{text}</span>
    </div>
  );
}
