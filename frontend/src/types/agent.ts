export type EligibilityVerdict = 'eligible' | 'likely_eligible' | 'likely_ineligible' | 'unknown';
export type PlanStatus = 'plan_ready' | 'need_more_info' | 'insufficient_data';

export interface UserProfile {
  age?: number;
  gender?: string;
  state?: string;
  occupation?: string;
  annual_income?: number;
  category?: string;
  has_land?: boolean;
  bpl?: boolean;
}

export interface EligibilityCheck {
  scheme: string;
  source_id: string;
  verdict: EligibilityVerdict;
  matched_criteria: string[];
  missing_criteria: string[];
  unknown_criteria: string[];
}

export interface ActionStep {
  order: number;
  action: string;
  where?: string | null;
  estimated_time?: string | null;
}

export interface AgentPlan {
  status: PlanStatus;
  eligibility: EligibilityCheck[];
  documents_needed: string[];
  steps: ActionStep[];
  clarifying_questions: string[];
  disclaimer: string;
}
