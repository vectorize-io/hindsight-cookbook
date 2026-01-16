// Side types
// 'front' | 'back' | 'middle' for easy mode and hard mode building interiors
// 'building_a' | 'building_b' | 'building_c' for medium mode
// 'street' for hard mode city grid navigation
export type Side = 'front' | 'back' | 'middle' | 'building_a' | 'building_b' | 'building_c' | 'street';

// Employee
export interface Employee {
  name: string;
  role: string;
  business: string;
  floor: number;
  side: Side;
  building?: string | null;  // Building name for hard mode (city grid)
}

// Package
export interface Package {
  id: string;
  recipientName: string;
  businessName?: string;
}

// Delivery status
export type DeliveryStatus = 'idle' | 'running' | 'success' | 'failed' | 'cancelled';

// Delivery
export interface Delivery {
  id: string;
  package: Package;
  status: DeliveryStatus;
  steps: number;
  startTime: number;
}

// Memory recall/reflect result from hindsight
export interface MemoryReflect {
  method: 'recall' | 'reflect';  // Which method was used
  query: string;                  // The query sent to hindsight
  context: string | null;         // The formatted memory context injected into prompt
  memories?: MemoryFact[];        // Raw facts (for recall mode)
  count: number;                  // Number of memories found
  timing?: number;                // Time taken in seconds
  error?: string | null;
}

// Individual memory fact from recall
export interface MemoryFact {
  text: string;
  type: string;  // world, experience, opinion
  weight: number;
}

// Message in the conversation
export interface Message {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: { id: string; function: { name: string; arguments: string } }[];
  tool_call_id?: string;
}

// Action entry in the log
export interface ActionEntry {
  step: number;
  toolName: string;
  toolArgs: Record<string, unknown>;
  toolResult: string;
  thinking?: string;
  floor: number;
  side: string;
  timing: number;
  messages?: Message[];  // Full conversation/prompt sent to LLM
  llmDetails?: {
    toolCalls: { name: string; arguments: string }[];
  };
  // Hard mode city grid fields
  gridRow?: number;
  gridCol?: number;
  currentBuilding?: string | null;
}

// Delivery result for history
export interface DeliveryResult {
  package: string;
  success: boolean;
  steps: number;
}

// Stats
export interface Stats {
  deliveriesCompleted: number;
  totalSteps: number;
  history: DeliveryResult[];
}

// WebSocket event types
export type ServerEventType =
  | 'connected'
  | 'delivery_started'
  | 'memory_reflect'
  | 'agent_thinking'
  | 'agent_action'
  | 'memory_storing'
  | 'memory_stored'
  | 'delivery_success'
  | 'delivery_failed'
  | 'step_limit_reached'
  | 'cancelled'
  | 'error';

export interface ServerEvent<T = unknown> {
  type: ServerEventType;
  payload?: T;
}

// Mode
export type Mode = 'ui' | 'ff' | 'eval';
