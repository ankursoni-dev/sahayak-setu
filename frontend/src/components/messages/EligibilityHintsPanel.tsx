import type { EligibilityHint } from '@/types/scheme';

function verdictEmoji(v: EligibilityHint['verdict']): string {
  if (v === 'likely_eligible') return '✅';
  if (v === 'likely_ineligible') return '❌';
  return '❓';
}

interface EligibilityHintsPanelProps {
  hints: readonly EligibilityHint[];
}

export function EligibilityHintsPanel({ hints }: EligibilityHintsPanelProps) {
  if (!hints.length) return null;
  return (
    <section className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
      <p className="eyebrow mb-3">Quick eligibility check (best-effort)</p>
      <ul className="flex flex-col gap-1.5">
        {hints.map((h, i) => (
          <li key={`${h.scheme}-${i}`} className="flex items-start gap-2 text-sm">
            <span aria-hidden="true">{verdictEmoji(h.verdict)}</span>
            <span>
              <span className="font-medium text-[var(--color-ink)]">{h.scheme}</span>
              {h.reason && <span className="text-[var(--color-ink-muted)]"> — {h.reason}</span>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
