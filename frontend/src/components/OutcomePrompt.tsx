import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { reportOutcome } from '@/lib/api';
import type { OutcomeValue } from '@/types/api';

/**
 * Returning-user outcome prompt (F8).
 *
 * On every render, asks the store for the oldest unresolved scheme that is at least
 * 6 hours old, and surfaces a 4-button card asking what happened. Posting the answer
 * marks the entry resolved (in the persisted store) and dismisses the card. Closing
 * with × also marks it resolved with "n/a" so the same scheme isn't re-prompted.
 */

const OPTIONS: { value: OutcomeValue; label: string }[] = [
  { value: 'applied', label: 'I applied' },
  { value: 'received', label: 'Got the benefit' },
  { value: 'rejected', label: 'I was rejected' },
  { value: 'not_applied', label: "Didn't apply" },
];

export function OutcomePrompt() {
  const sessionUserId = useAppStore((s) => s.sessionUserId);
  const resolvePendingOutcome = useAppStore((s) => s.resolvePendingOutcome);
  // Subscribing to pendingOutcomes (not nextPromptableOutcome directly) ensures the
  // component re-renders whenever the list mutates — getter results are stable in
  // the snapshot but Zustand can't track them as selector values.
  const pendingOutcomes = useAppStore((s) => s.pendingOutcomes);
  const nextPromptableOutcome = useAppStore((s) => s.nextPromptableOutcome);

  const [busy, setBusy] = useState(false);
  // Recompute every minute so a card that becomes eligible mid-session appears
  // without a page reload, but without re-renders flooding when nothing changed.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const target = nextPromptableOutcome();
  if (!target) return null;
  // Reading pendingOutcomes triggers re-render on store mutation; the variable itself
  // isn't otherwise used.
  void pendingOutcomes;

  const submit = (outcome: OutcomeValue) => {
    if (busy) return;
    setBusy(true);
    reportOutcome({
      scheme: target.scheme,
      outcome,
      trace_id: target.trace_id,
      session_user_id: sessionUserId || null,
    });
    resolvePendingOutcome(target.scheme);
    setBusy(false);
  };

  const dismiss = () => {
    // Mark resolved with "n/a" so the user isn't re-prompted, and tell the backend
    // (best-effort) so the analytics aggregate distinguishes "didn't engage" from
    // "didn't apply".
    submit('n/a');
  };

  return (
    <aside
      role="region"
      aria-label="Outcome prompt"
      className="mb-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-peach-faint)] p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="eyebrow">Quick check-in</p>
          <p className="text-sm text-[var(--color-ink)]">
            You looked into <span className="font-semibold">{target.scheme}</span> earlier.
            What happened?
          </p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss outcome prompt"
          disabled={busy}
          className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[var(--color-ink-muted)] hover:bg-white"
        >
          <X size={14} strokeWidth={2} />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            disabled={busy}
            onClick={() => submit(opt.value)}
            className="rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--color-ink)] transition-colors hover:border-[var(--color-ink)] disabled:opacity-50"
          >
            {opt.label}
          </button>
        ))}
      </div>
    </aside>
  );
}
