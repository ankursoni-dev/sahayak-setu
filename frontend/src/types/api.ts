import type { SchemeSource, EligibilityHint, QueryDebug } from './scheme';
import type { AgentPlan, UserProfile } from './agent';

export interface SearchRequest {
  query: string;
  user_id?: string;
  language: string;
  profile?: Partial<UserProfile> | null;
  include_plan?: boolean;
}

export interface SearchResponse {
  answer: string | null;
  provider: string | null;
  sources: SchemeSource[];
  moderation_blocked: boolean;
  redirect_message: string | null;
  moderation_category: string | null;
  reasoning_why: string | null;
  near_miss_text: string | null;
  near_miss_sources: SchemeSource[];
  session_user_id: string | null;
  confidence: 'high' | 'medium' | 'low' | null;
  next_step: string | null;
  retrieval_debug: Record<string, unknown> | null;
  query_debug: QueryDebug | null;
  plan: AgentPlan | null;
  eligibility_hints: EligibilityHint[];
  timing_ms?: Record<string, number> | null;
}

export interface FeedbackRequest {
  value: 'up' | 'down';
  trace_id: string | null;
  session_user_id: string;
  query_preview: string;
  answer_preview: string;
}

export interface ErrorReport {
  error: string;
  trace_id: string | null;
  language: string;
  query_prefix: string;
}
