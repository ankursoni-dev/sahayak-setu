interface ConfidenceArcProps {
  confidence: 'high' | 'medium' | 'low' | null | undefined;
  score: number | null | undefined;
}

function meta(confidence: ConfidenceArcProps['confidence'], score: number) {
  const s = Math.max(0, Math.min(1, score));
  if (confidence === 'high') return { status: 'verified', label: 'VERIFIED', score: s, grounded: 'Grounded match' };
  if (confidence === 'medium') return { status: 'partial', label: 'PARTIAL', score: s, grounded: 'Needs verification' };
  return { status: 'unverified', label: 'UNVERIFIED', score: s, grounded: 'Needs more profile info' };
}

const STATUS_COLOR: Record<string, string> = {
  verified: 'var(--color-success)',
  partial: 'var(--color-warn)',
  unverified: 'var(--color-ink-subtle)',
};

export function ConfidenceArc({ confidence, score }: ConfidenceArcProps) {
  const m = meta(confidence, typeof score === 'number' ? score : 0);
  const pct = Math.round(m.score * 100);
  return (
    <div
      className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3 w-fit"
      role="img"
      aria-label={`${m.label}, retrieval match about ${pct} percent. ${m.grounded}`}
    >
      <svg viewBox="0 0 64 64" width={42} height={42} aria-hidden="true">
        <path
          d="M 8 44 A 24 24 0 1 1 56 44"
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d="M 8 44 A 24 24 0 1 1 56 44"
          fill="none"
          stroke={STATUS_COLOR[m.status]}
          strokeWidth="6"
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray={`${pct} 100`}
          style={{ transition: 'stroke-dasharray 0.5s ease' }}
        />
      </svg>
      <div className="flex flex-col leading-tight">
        <span className="text-xs font-semibold tracking-wide" style={{ color: STATUS_COLOR[m.status] }}>
          {m.label}
        </span>
        <span className="text-xs text-[var(--color-ink-muted)]">{m.grounded}</span>
        <span className="text-xs text-[var(--color-ink-subtle)]">{m.score.toFixed(2)} match</span>
      </div>
    </div>
  );
}
