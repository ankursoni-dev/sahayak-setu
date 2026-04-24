import type { AgentPlan, EligibilityCheck } from '@/types/agent';
import { cn } from '@/lib/cn';

const VERDICT_CLASS: Record<string, string> = {
  eligible: 'bg-[var(--color-success)]/10 text-[var(--color-success)]',
  likely_eligible: 'bg-[var(--color-warn)]/10 text-[var(--color-warn)]',
  likely_ineligible: 'bg-[var(--color-error)]/10 text-[var(--color-error)]',
  unknown: 'bg-[var(--color-surface-2)] text-[var(--color-ink-muted)]',
};

interface ActionPlanPanelProps {
  plan: AgentPlan | null | undefined;
}

export function ActionPlanPanel({ plan }: ActionPlanPanelProps) {
  if (!plan) return null;
  const { eligibility = [], documents_needed = [], steps = [], clarifying_questions = [], disclaimer = '' } = plan;
  const hasBody =
    eligibility.length || documents_needed.length || steps.length || clarifying_questions.length || disclaimer;
  if (!hasBody) return null;

  const statusLabel = plan.status ? plan.status.replaceAll('_', ' ') : 'plan';

  return (
    <section
      className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5"
      aria-label="Action plan"
    >
      <header className="mb-4 flex items-center justify-between gap-2">
        <span className="eyebrow">Action plan</span>
        <span className="rounded-full bg-[var(--color-surface)] px-2.5 py-0.5 text-xs font-medium text-[var(--color-ink-muted)]">
          {statusLabel}
        </span>
      </header>

      {eligibility.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)]">
            Eligibility snapshot
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {eligibility.slice(0, 6).map((row: EligibilityCheck, i) => (
              <article
                key={i}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] p-3"
              >
                <span
                  className={cn(
                    'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
                    VERDICT_CLASS[row.verdict] ?? VERDICT_CLASS.unknown,
                  )}
                >
                  {row.verdict.replaceAll('_', ' ')}
                </span>
                <h4 className="mt-1.5 font-medium text-[var(--color-ink)] text-sm">{row.scheme}</h4>
                {row.source_id && <p className="text-xs text-[var(--color-ink-subtle)]">Source {row.source_id}</p>}
              </article>
            ))}
          </div>
        </div>
      )}

      {documents_needed.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)]">
            Documents to keep ready
          </p>
          <div className="flex flex-wrap gap-1.5">
            {documents_needed.slice(0, 10).map((d, i) => (
              <span
                key={`${d}-${i}`}
                className="rounded-full bg-[var(--color-surface)] px-3 py-1 text-xs text-[var(--color-ink)]"
              >
                {d}
              </span>
            ))}
          </div>
        </div>
      )}

      {steps.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)]">Steps</p>
          <ol className="flex flex-col gap-2.5">
            {steps.slice(0, 8).map((step, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <span className="mt-0.5 inline-flex h-6 w-6 flex-none items-center justify-center rounded-full bg-[var(--color-cta)] text-xs font-semibold text-[var(--color-cta-ink)]">
                  {step.order ?? idx + 1}
                </span>
                <div className="flex-1">
                  <p className="font-medium text-[var(--color-ink)] text-sm">{step.action}</p>
                  {(step.where || step.estimated_time) && (
                    <p className="text-xs text-[var(--color-ink-muted)]">
                      {step.where && <span>{step.where}</span>}
                      {step.where && step.estimated_time && <span> · </span>}
                      {step.estimated_time && <span>{step.estimated_time}</span>}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {clarifying_questions.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)]">
            To tailor this further
          </p>
          <ul className="flex flex-col gap-1 list-disc pl-5 text-sm text-[var(--color-ink)]">
            {clarifying_questions.slice(0, 5).map((q, i) => (
              <li key={`${q}-${i}`}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      {disclaimer && (
        <footer className="border-t border-[var(--color-border)] pt-3 text-xs text-[var(--color-ink-subtle)]">
          {disclaimer}
        </footer>
      )}
    </section>
  );
}
