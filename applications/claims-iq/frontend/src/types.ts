export type AgentMode = 'no_memory' | 'recall' | 'reflect' | 'hindsight_mm';

export type PipelineStage = 'received' | 'classified' | 'verified' | 'routed' | 'resolved';

export interface Claim {
  claimId: string;
  scenarioId: string;
  category: string;
  description: string;
  policyId: string;
  region: string;
  amount: number;
  claimantName: string;
  incidentDate: string;
}

export interface AgentAction {
  step: number;
  toolName: string;
  toolArgs: Record<string, unknown>;
  toolResult: string;
  thinking?: string | null;
  timing: number;
}

export interface MemoryInjection {
  method: string;
  query: string;
  text: string | null;
  count: number;
  timing: number;
}

export interface AgentMistake {
  step: number;
  description: string;
}

export interface ClaimResult {
  claimId: string;
  category: string;
  decision: string;
  correct: boolean;
  steps: number;
  optimalSteps: number;
  reworkCount: number;
  mistakes: AgentMistake[];
  expectedWorkflow: string[];
  actualWorkflow: string[];
}

export interface MentalModel {
  id: string;
  name: string;
  source_query: string;
  content?: string;
  last_refreshed?: string;
  observations?: unknown[];
}

export interface ServerEvent {
  type: string;
  payload?: Record<string, unknown>;
}
