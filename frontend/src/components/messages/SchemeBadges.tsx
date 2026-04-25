import type { SchemeSource } from '@/types/scheme';

/**
 * Small pill row rendered under each retrieved scheme in the answer view:
 *
 *   [✓ Available in Karnataka]  [Verified 12 Mar 2026]  [Matched: kisan, loan]
 *
 * Each pill is independent — any of them can be absent. Components rendering scheme
 * lists should drop in <SchemeBadges source={s} /> below the scheme name.
 */
interface SchemeBadgesProps {
  source: SchemeSource;
}

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
] as const;

function formatVerified(iso: string | null | undefined): string | null {
  if (!iso) return null;
  // Accept "YYYY-MM-DD" with no time portion. Reject anything we can't parse so we
  // don't render "Invalid Date" to the user.
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const year = m[1];
  const month = MONTHS[Number(m[2]) - 1];
  const day = String(Number(m[3]));
  if (!year || !month) return null;
  return `Verified ${day} ${month} ${year}`;
}

function stateLabel(source: SchemeSource): { label: string; tone: 'green' | 'amber' | 'red' } | null {
  switch (source.state_match) {
    case 'available':
      return { label: 'Available in your state', tone: 'green' };
    case 'not_available': {
      const states =
        Array.isArray(source.state_availability) && source.state_availability.length
          ? source.state_availability.join(', ')
          : null;
      return {
        label: states ? `Only in ${states}` : 'Not available in your state',
        tone: 'red',
      };
    }
    case 'unknown_state':
      return { label: 'Availability unverified', tone: 'amber' };
    default:
      return null;
  }
}

const TONE_CLASS: Record<'green' | 'amber' | 'red' | 'neutral', string> = {
  green: 'bg-[var(--color-peach-faint)] text-[var(--color-ink)]',
  amber: 'bg-[rgba(234,122,31,0.12)] text-[var(--color-ink)]',
  red: 'bg-[rgba(220,38,38,0.10)] text-[#9b1c1c]',
  neutral: 'bg-[var(--color-surface)] text-[var(--color-ink-muted)]',
};

export function SchemeBadges({ source }: SchemeBadgesProps) {
  const verified = formatVerified(source.last_verified_at);
  const state = stateLabel(source);
  const matched = (source.matched_terms ?? []).slice(0, 3);
  if (!verified && !state && !matched.length) return null;

  return (
    <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
      {state && (
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 ${TONE_CLASS[state.tone]}`}>
          {state.label}
        </span>
      )}
      {verified && (
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 ${TONE_CLASS.neutral}`}>
          {verified}
        </span>
      )}
      {matched.length > 0 && (
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 ${TONE_CLASS.neutral}`}
          title={`Matched on: ${matched.join(', ')}`}
        >
          Matched: {matched.join(', ')}
        </span>
      )}
    </div>
  );
}
