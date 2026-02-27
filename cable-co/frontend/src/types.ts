export type AgentMode = 'memory_off' | 'memory_on';

export interface CustomerScenario {
  scenarioIndex: number;
  accountId: string;
  customerMessage: string;
  category: string;
  customerName: string;
  planName: string;
  tenure: number;
  contractMonths: number;
  area: string;
  learningPairId: string | null;
  isLearningTest: boolean;
}

export interface AgentAction {
  step: number;
  toolName: string;
  toolArgs: Record<string, unknown>;
  toolResult: string;
  thinking?: string | null;
  timing: number;
  isAction: boolean;
  isLookup: boolean;
  rejected: boolean;
  rejectionFeedback: string | null;
}

/** A pending suggestion waiting for CSR approval */
export interface PendingSuggestion {
  suggestionId: string;
  step: number;
  toolName: string;
  toolArgs: Record<string, unknown>;
  reasoning: string;
  rejectionHint: string | null;
}

export interface MemoryRecall {
  method: string;
  query: string;
  text: string | null;
  count: number;
  timing: number;
}

export interface Rejection {
  step: number;
  tool: string;
  feedback: string;
}

export interface KnowledgeRule {
  tool: string;
  feedback: string;
  step: number;
}

export interface ScenarioResult {
  scenarioIndex: number;
  accountId: string;
  category: string;
  steps: number;
  rejections: Rejection[];
  rejectionCount: number;
  learningPairId: string | null;
  isLearningTest: boolean;
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
