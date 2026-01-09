// Side types
export type Side = 'front' | 'back' | 'middle';

// Employee
export interface Employee {
  name: string;
  role: string;
  business: string;
  floor: number;
  side: Side;
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

// Memory injection info
export interface MemoryInjection {
  injected: boolean;
  count: number;
  context?: string;
  bankId?: string;
  query?: string;
  error?: string | null;
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
  memoryInjection?: MemoryInjection;
  llmDetails?: {
    toolCalls: { name: string; arguments: string }[];
  };
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
