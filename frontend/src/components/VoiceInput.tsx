import { Mic, Square } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { cn } from '@/lib/cn';

interface VoiceInputProps {
  active: boolean;
  dbLevel: number;
  liveCaption: string;
  onToggle: () => void;
}

export function VoiceInput({ active, dbLevel, liveCaption, onToggle }: VoiceInputProps) {
  const voiceState = useAppStore((s) => s.voiceState);
  const hint = resolveHint(voiceState);

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        onClick={onToggle}
        aria-label={active ? 'Stop voice' : 'Start voice'}
        aria-pressed={active}
        className={cn(
          'group relative flex h-20 w-20 items-center justify-center rounded-full transition-all',
          active
            ? 'bg-[var(--color-saffron)] text-white shadow-[0_0_0_8px_rgba(234,122,31,0.14)]'
            : 'bg-[var(--color-cta)] text-[var(--color-cta-ink)] shadow-md hover:shadow-lg hover:scale-105',
        )}
      >
        {active ? <Square size={24} fill="currentColor" strokeWidth={0} /> : <Mic size={24} strokeWidth={2} />}
        {active && <WaveformRing />}
      </button>
      <div className="text-center">
        <div className="text-sm font-medium text-[var(--color-ink)]">{active ? 'Stop' : 'Talk'}</div>
        <div className="text-xs text-[var(--color-ink-muted)]">{hint}</div>
      </div>
      {active && (
        <div
          className="h-1.5 w-48 overflow-hidden rounded-full bg-[var(--color-surface-2)]"
          role="meter"
          aria-label="Microphone level"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(dbLevel * 100)}
        >
          <div
            className="h-full bg-[var(--color-saffron)] transition-[width] duration-75 ease-out"
            style={{ width: `${Math.max(8, dbLevel * 100)}%` }}
          />
        </div>
      )}
      {liveCaption && (
        <p className="max-w-md text-center text-sm italic text-[var(--color-ink-muted)]" aria-live="polite">
          {liveCaption}
        </p>
      )}
    </div>
  );
}

function WaveformRing() {
  return (
    <span className="pointer-events-none absolute inset-0 inline-flex items-center justify-center">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="mx-[1.5px] inline-block w-[3px] rounded-full bg-white/90"
          style={{
            height: `${12 + (i % 3) * 6}px`,
            animation: `wave-bar 1s ${i * 0.12}s ease-in-out infinite`,
            transformOrigin: 'center',
          }}
        />
      ))}
    </span>
  );
}

function resolveHint(state: string): string {
  switch (state) {
    case 'listening':
      return 'Listening… tap to stop';
    case 'thinking':
      return 'Processing your question…';
    case 'speaking':
      return 'Speaking your answer…';
    default:
      return 'Choose language and tap to speak';
  }
}
