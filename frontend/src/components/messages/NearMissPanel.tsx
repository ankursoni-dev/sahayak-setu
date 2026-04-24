import type { SchemeSource } from '@/types/scheme';
import { SourceLinksBlock } from './SourceLinksBlock';

interface NearMissPanelProps {
  text: string | null | undefined;
  sources: readonly SchemeSource[];
}

export function NearMissPanel({ text, sources }: NearMissPanelProps) {
  const hasText = text && text.trim();
  if (!hasText && !sources.length) return null;
  return (
    <section className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <header className="mb-2">
        <span className="eyebrow">Possible mismatch — what to check next</span>
      </header>
      {hasText && <p className="text-sm text-[var(--color-ink)]">{text!.trim()}</p>}
      {sources.length > 0 && <SourceLinksBlock sources={sources} heading="Related references (lower match)" />}
    </section>
  );
}
