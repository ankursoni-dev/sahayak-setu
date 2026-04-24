import { useState } from 'react';
import { useAppStore } from '@/store/appStore';

interface LastQueryBannerProps {
  onAskAgain: (query: string) => void;
}

export function LastQueryBanner({ onAskAgain }: LastQueryBannerProps) {
  const lastQuery = useAppStore((s) => s.lastQuery);
  const hasMessages = useAppStore((s) => s.messages.length > 0);
  const [dismissed, setDismissed] = useState(false);

  if (!lastQuery || hasMessages || dismissed) return null;
  const preview = lastQuery.length > 55 ? `${lastQuery.slice(0, 55)}…` : lastQuery;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-peach-faint)] px-4 py-3">
      <span className="text-sm text-[var(--color-ink)]">
        <span className="eyebrow mr-2">Last time</span>"{preview}"
      </span>
      <button
        type="button"
        onClick={() => {
          setDismissed(true);
          onAskAgain(lastQuery);
        }}
        className="text-sm font-medium text-[var(--color-saffron)] hover:underline"
      >
        Ask again →
      </button>
    </div>
  );
}
