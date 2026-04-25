import { useEffect, useState } from 'react';
import { CURATED_SCHEMES, type CuratedScheme } from '@/data/curatedSchemes';
import { fetchFeaturedSchemes } from '@/lib/api';
import { useAppStore } from '@/store/appStore';
import { SchemeCard } from './SchemeCard';

interface SchemesGridProps {
  onOpen: (scheme: CuratedScheme) => void;
  onCheckEligibility: (scheme: CuratedScheme) => void;
}

const HOT_COUNT = 5; // first N cards are pinned national flagships

/**
 * Home-page grid. On mount (and whenever the user's selected state changes via the
 * Eligibility Finder) we hit /api/v2/featured for live data. Until that resolves, we
 * render the hand-curated fallback list so the page never goes blank — and if the
 * fetch fails we keep the fallback rather than blowing the section up.
 */
export function SchemesGrid({ onOpen, onCheckEligibility }: SchemesGridProps) {
  const finderState = useAppStore((s) => s.lastFinderProfile?.state ?? null);
  const [schemes, setSchemes] = useState<CuratedScheme[]>(CURATED_SCHEMES);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchFeaturedSchemes(finderState, 12)
      .then((resp) => {
        if (cancelled) return;
        if (Array.isArray(resp.items) && resp.items.length > 0) {
          // Map the API shape onto CuratedScheme. Optional fields the static list
          // carried (ministryFamily, defaultRole) are intentionally omitted —
          // they're only used by code paths that aren't on the dynamic flow.
          setSchemes(
            resp.items.map((it) => ({
              id: it.id,
              slug: it.slug,
              name: it.name,
              emoji: it.emoji,
              summary: it.summary,
              ministry: it.ministry,
              benefit: it.benefit,
              eligibility: it.eligibility,
              applyLink: it.applyLink,
              sourceLink: it.sourceLink,
              level: it.level ?? undefined,
              state: it.state,
            })),
          );
        }
      })
      .catch(() => {
        // Stay on the hardcoded fallback — better than an empty grid.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [finderState]);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {schemes.map((s, idx) => (
        <SchemeCard
          key={s.id}
          scheme={s}
          isHot={idx < HOT_COUNT}
          onOpen={onOpen}
          onCheckEligibility={onCheckEligibility}
        />
      ))}
      {loading && schemes.length === 0 && (
        <div className="col-span-full text-center text-sm text-[var(--color-ink-muted)]">Loading…</div>
      )}
    </div>
  );
}
