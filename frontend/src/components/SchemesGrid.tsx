import { CURATED_SCHEMES, type CuratedScheme } from '@/data/curatedSchemes';
import { SchemeCard } from './SchemeCard';

interface SchemesGridProps {
  onOpen: (scheme: CuratedScheme) => void;
  onCheckEligibility: (scheme: CuratedScheme) => void;
}

export function SchemesGrid({ onOpen, onCheckEligibility }: SchemesGridProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {CURATED_SCHEMES.map((s) => (
        <SchemeCard key={s.id} scheme={s} onOpen={onOpen} onCheckEligibility={onCheckEligibility} />
      ))}
    </div>
  );
}
