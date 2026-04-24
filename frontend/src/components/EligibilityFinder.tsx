import { useState, type FormEvent } from 'react';
import { INDIAN_STATES } from '@/data/states';
import { useAppStore } from '@/store/appStore';
import type { UserProfile } from '@/types/agent';

const ROLES = ['farmer', 'woman', 'student', 'artisan', 'senior citizen', 'below poverty line household'] as const;
const INCOME_BANDS = ['below 1 lakh', '1 to 3 lakh', '3 to 6 lakh', 'above 6 lakh'] as const;

function incomeToAnnual(band: string): number | null {
  const v = band.toLowerCase();
  if (v.includes('below 1')) return 50_000;
  if (v.includes('1 to 3')) return 200_000;
  if (v.includes('3 to 6')) return 450_000;
  if (v.includes('above 6')) return 800_000;
  return null;
}

function buildQuery(role: string, state: string, income: string): string {
  return `Show government welfare schemes for a ${role} in ${state} with annual family income ${income}. Summarise the most relevant central or state schemes and how to apply.`;
}

interface EligibilityFinderProps {
  onSubmit: (query: string, profile: Partial<UserProfile>) => void;
  defaultRole?: (typeof ROLES)[number];
}

export function EligibilityFinder({ onSubmit, defaultRole = 'farmer' }: EligibilityFinderProps) {
  const setFinderProfile = useAppStore((s) => s.setFinderProfile);
  const [state, setState] = useState<string>('Karnataka');
  const [role, setRole] = useState<string>(defaultRole);
  const [income, setIncome] = useState<string>('below 1 lakh');

  const onFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    const profile: Partial<UserProfile> = { state, occupation: role };
    const annual = incomeToAnnual(income);
    if (annual != null) profile.annual_income = annual;
    if (role.toLowerCase().includes('below poverty')) profile.bpl = true;
    setFinderProfile(profile);
    onSubmit(buildQuery(role, state, income), profile);
  };

  return (
    <form onSubmit={onFormSubmit} className="flex flex-col gap-5 card-soft p-6">
      <div>
        <h2 className="text-2xl">Eligibility finder</h2>
        <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
          Tell us a little about you — we'll find schemes in plain language.
        </p>
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="eyebrow">State</span>
        <select
          value={state}
          onChange={(e) => setState(e.target.value)}
          required
          className="rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] px-3 py-2.5 text-sm focus:border-[var(--color-ink)] outline-none"
        >
          {INDIAN_STATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <fieldset>
        <legend className="eyebrow mb-2">I am a</legend>
        <div className="flex flex-wrap gap-2">
          {ROLES.map((r) => (
            <ChipRadio
              key={r}
              name="finderRole"
              value={r}
              label={r}
              checked={role === r}
              onChange={() => setRole(r)}
            />
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="eyebrow mb-2">Annual family income</legend>
        <div className="flex flex-wrap gap-2">
          {INCOME_BANDS.map((b) => (
            <ChipRadio
              key={b}
              name="finderIncome"
              value={b}
              label={formatIncome(b)}
              checked={income === b}
              onChange={() => setIncome(b)}
            />
          ))}
        </div>
      </fieldset>

      <button type="submit" className="btn-cta self-start">
        Search schemes
      </button>
    </form>
  );
}

function formatIncome(band: string): string {
  if (band === 'below 1 lakh') return '< ₹1L';
  if (band === '1 to 3 lakh') return '₹1–3L';
  if (band === '3 to 6 lakh') return '₹3–6L';
  if (band === 'above 6 lakh') return '₹6L+';
  return band;
}

function ChipRadio({
  name,
  value,
  label,
  checked,
  onChange,
}: {
  name: string;
  value: string;
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors ${
        checked
          ? 'border-[var(--color-ink)] bg-[var(--color-cta)] text-[var(--color-cta-ink)]'
          : 'border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-[var(--color-ink-muted)] hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]'
      }`}
    >
      <input type="radio" name={name} value={value} checked={checked} onChange={onChange} className="sr-only" />
      <span className="capitalize">{label}</span>
    </label>
  );
}
