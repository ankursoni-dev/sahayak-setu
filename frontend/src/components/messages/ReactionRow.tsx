import { useState, type MouseEvent } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { cn } from '@/lib/cn';
import { sendFeedback } from '@/lib/api';
import { useAppStore } from '@/store/appStore';

interface ReactionRowProps {
  queryPreview: string;
  answerPreview: string;
}

export function ReactionRow({ queryPreview, answerPreview }: ReactionRowProps) {
  const [selected, setSelected] = useState<'up' | 'down' | null>(null);
  const [confetti, setConfetti] = useState(false);
  const sessionUserId = useAppStore((s) => s.sessionUserId);
  const traceId = useAppStore((s) => s.lastTraceId);

  const onReact = (value: 'up' | 'down', e: MouseEvent<HTMLButtonElement>) => {
    setSelected(value);
    sendFeedback({
      value,
      trace_id: traceId,
      session_user_id: sessionUserId,
      query_preview: queryPreview.slice(0, 100),
      answer_preview: answerPreview.slice(0, 200),
    });
    if (value === 'up') {
      setConfetti(true);
      const btn = e.currentTarget;
      fireConfetti(btn);
      window.setTimeout(() => setConfetti(false), 800);
    }
  };

  const shareText = `SahayakSetu (सहायक सेतु) found this:\n\n${answerPreview.slice(0, 200)}…\n\nAsk about govt schemes: https://sahayaksetu.vercel.app`;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
      <span className="text-xs text-[var(--color-ink-muted)]">Helpful?</span>
      <button
        type="button"
        onClick={(e) => onReact('up', e)}
        aria-label="Thumbs up"
        aria-pressed={selected === 'up'}
        className={cn(
          'relative inline-flex h-8 w-8 items-center justify-center rounded-full border transition-colors',
          selected === 'up'
            ? 'border-[var(--color-saffron)] bg-[var(--color-peach-faint)] text-[var(--color-saffron)]'
            : 'border-[var(--color-border)] text-[var(--color-ink-muted)] hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]',
        )}
      >
        <ThumbsUp size={14} strokeWidth={2} />
      </button>
      <button
        type="button"
        onClick={(e) => onReact('down', e)}
        aria-label="Thumbs down"
        aria-pressed={selected === 'down'}
        className={cn(
          'inline-flex h-8 w-8 items-center justify-center rounded-full border transition-colors',
          selected === 'down'
            ? 'border-[var(--color-ink)] bg-[var(--color-surface)] text-[var(--color-ink)]'
            : 'border-[var(--color-border)] text-[var(--color-ink-muted)] hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]',
        )}
      >
        <ThumbsDown size={14} strokeWidth={2} />
      </button>
      {selected === 'up' && (
        <a
          href={`https://wa.me/?text=${encodeURIComponent(shareText)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-[#25D366] px-3 py-1.5 text-xs font-medium text-white transition-transform hover:scale-105"
        >
          📱 Share
        </a>
      )}
      {confetti && <span className="sr-only">Thanks for the feedback!</span>}
    </div>
  );
}

function fireConfetti(btn: HTMLElement) {
  const colors = ['#ea7a1f', '#f2a33a', '#fde68a', '#2ecc71', '#5dade2', '#e74c3c'];
  const burst = document.createElement('div');
  burst.style.cssText = 'position:absolute;top:50%;left:50%;pointer-events:none;z-index:50;';
  for (let i = 0; i < 8; i++) {
    const p = document.createElement('span');
    const angle = (i / 8) * 360;
    const dist = 28 + Math.random() * 18;
    const tx = Math.round(Math.cos((angle * Math.PI) / 180) * dist);
    const ty = Math.round(Math.sin((angle * Math.PI) / 180) * dist);
    p.style.cssText = `position:absolute;width:6px;height:6px;border-radius:50%;background:${colors[i % colors.length]};--tx:${tx}px;--ty:${ty}px;animation:confetti-fly 0.65s ease-out forwards;`;
    burst.appendChild(p);
  }
  const wrapper = btn.closest('.reaction-row-wrap') ?? btn;
  if (wrapper instanceof HTMLElement) {
    wrapper.style.position = 'relative';
    wrapper.appendChild(burst);
    window.setTimeout(() => burst.remove(), 800);
  }
}
