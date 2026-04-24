export interface SchemeSource {
  scheme: string;
  score: number;
  apply_link?: string | null;
  source?: string | null;
  confidence_label: string;
  cta_label: string;
  preview_text: string;
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
