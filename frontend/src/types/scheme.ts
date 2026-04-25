export interface SchemeSource {
  scheme: string;
  score: number;
  apply_link?: string | null;
  source?: string | null;
  confidence_label: string;
  cta_label: string;
  preview_text: string;
  // ISO date the chunk was last verified against the official source.
  last_verified_at?: string | null;
  // "all" or a list of state names; absent when not yet curated.
  state_availability?: 'all' | string[] | null;
  // Server-computed match against the user's profile.state when present.
  state_match?: 'available' | 'not_available' | 'unknown_state' | null;
  // Up to 4 query tokens that overlapped the chunk.
  matched_terms?: string[];
}

export interface EligibilityHint {
  scheme: string;
  verdict: 'likely_eligible' | 'likely_ineligible' | 'unknown';
  reason: string;
}

export interface QueryDebug {
  original?: string;
  rewritten?: string;
}
