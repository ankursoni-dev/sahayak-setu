import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { SearchResponse } from '@/types/api';
import { AnswerBody } from './AnswerBody';
import { ConfidenceArc } from './ConfidenceArc';
import { QueryUnderstandingPill } from './QueryUnderstandingPill';
import { CitationFootnotes } from './CitationFootnotes';
import { ExplainPanel } from './ExplainPanel';
import { NearMissPanel } from './NearMissPanel';
import { EligibilityHintsPanel } from './EligibilityHintsPanel';
import { SourceLinksBlock } from './SourceLinksBlock';
import { NextStepPanel } from './NextStepPanel';
import { ActionPlanPanel } from './ActionPlanPanel';
import { ReactionRow } from './ReactionRow';

interface AssistantMessageProps {
  payload: SearchResponse;
  content: string;
  /** Voice turns get a compact layout — answer only, with a "Show details" toggle
   * that reveals citations, eligibility hints, and action plan on demand. */
  compact?: boolean;
}

export function AssistantMessage({ payload, content, compact = false }: AssistantMessageProps) {
  const [expanded, setExpanded] = useState(false);
  const topScore = payload.sources.length
    ? Math.max(...payload.sources.map((s) => s.score ?? 0))
    : null;
  const queryPreview = payload.query_debug?.original ?? '';
  const showDetails = !compact || expanded;
  const hasDetails =
    payload.sources.length > 0 ||
    (payload.reasoning_why && payload.reasoning_why.trim()) ||
    (payload.near_miss_text && payload.near_miss_text.trim()) ||
    payload.near_miss_sources.length > 0 ||
    payload.eligibility_hints.length > 0 ||
    (payload.next_step && payload.next_step.trim()) ||
    Boolean(payload.plan);

  return (
    <div className="reaction-row-wrap flex flex-col gap-3">
      {showDetails && (
        <div className="flex flex-wrap items-center gap-3">
          {payload.confidence && <ConfidenceArc confidence={payload.confidence} score={topScore} />}
          <QueryUnderstandingPill queryDebug={payload.query_debug} />
        </div>
      )}

      <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 shadow-sm">
        <AnswerBody text={content} sources={showDetails ? payload.sources : []} />
      </div>

      {compact && !expanded && hasDetails && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="inline-flex w-fit items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--color-ink-muted)] transition-colors hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]"
        >
          Show details <ChevronDown size={12} strokeWidth={2.5} />
        </button>
      )}

      {showDetails && (
        <>
          <CitationFootnotes sources={payload.sources} />
          <ExplainPanel text={payload.reasoning_why} />
          <NearMissPanel text={payload.near_miss_text} sources={payload.near_miss_sources} />
          <EligibilityHintsPanel hints={payload.eligibility_hints} />
          <SourceLinksBlock sources={payload.sources} heading="Where this answer comes from" />
          <NextStepPanel text={payload.next_step} />
          <ActionPlanPanel plan={payload.plan} />
          <ReactionRow queryPreview={queryPreview} answerPreview={content} />
          {compact && expanded && (
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="inline-flex w-fit items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--color-ink-muted)] transition-colors hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]"
            >
              Hide details <ChevronUp size={12} strokeWidth={2.5} />
            </button>
          )}
        </>
      )}
    </div>
  );
}
