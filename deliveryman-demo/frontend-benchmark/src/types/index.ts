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
  | 'error'
  // Benchmark events
  | 'benchmark_start'
  | 'benchmark_progress'
  | 'benchmark_complete'
  | 'delivery_start'
  | 'models_refreshing'
  | 'models_refreshed';

export interface ServerEvent<T = unknown> {
  type: ServerEventType;
  payload?: T;
}

// Mode
export type Mode = 'ui' | 'ff' | 'eval';

// =============================================================================
// Benchmark Types
// =============================================================================

// Agent modes for benchmarking
export type AgentMode =
  | 'no_memory'  // Stateless baseline
  | 'filesystem'  // Agent manages own notes
  | 'recall'  // Hindsight recall - raw facts
  | 'reflect'  // Hindsight reflect - LLM synthesis
  | 'hindsight_mm'  // Mental models with wait
  | 'hindsight_mm_nowait';  // Mental models without wait

// Memory query mode
export type MemoryQueryMode = 'inject_once' | 'per_step' | 'both';

// Include business option
export type IncludeBusiness = 'always' | 'never' | 'random';

// Benchmark configuration
export interface BenchmarkConfig {
  mode: AgentMode;
  model: string;
  numDeliveries: number;
  repeatRatio: number;  // 0.0-1.0
  pairedMode: boolean;  // Each office visited exactly 2x
  includeBusiness: IncludeBusiness;
  stepMultiplier: number;  // max_steps = optimal * multiplier
  minSteps: number;
  memoryQueryMode: MemoryQueryMode;
  waitForConsolidation: boolean;
  refreshInterval: number;  // 0 = disabled
  difficulty: string;
  seed?: number;  // For reproducibility
}

// Token usage
export interface TokenUsage {
  prompt: number;
  completion: number;
  total: number;
}

// Metrics for a single delivery
export interface DeliveryMetrics {
  deliveryId: number;
  recipient: string;
  business?: string;
  success: boolean;
  stepsTaken: number;
  optimalSteps: number;
  pathEfficiency: number;
  tokens: TokenUsage;
  latencyMs: number;
  memoryInjected: boolean;
  memoryQueryCount: number;
  consolidationTriggered: boolean;
  isRepeat: boolean;
}

// Benchmark results summary
export interface BenchmarkSummary {
  totalDeliveries: number;
  successfulDeliveries: number;
  failedDeliveries: number;
  successRate: number;
  totalSteps: number;
  totalOptimalSteps: number;
  avgPathEfficiency: number;
  totalTokens: TokenUsage;
  totalLatencyMs: number;
  avgLatencyMs: number;
}

// Learning metrics
export interface LearningMetrics {
  convergenceEpisode: number;  // First episode with >= 90% efficiency
  firstHalfEfficiency: number;
  secondHalfEfficiency: number;
  improvement: number;  // second - first
}

// Time series data
export interface TimeSeries {
  efficiencyByEpisode: number[];
  tokensByEpisode: number[];
}

// Complete benchmark results
export interface BenchmarkResults {
  config: {
    mode: AgentMode;
    model: string;
    numDeliveries: number;
    repeatRatio: number;
    pairedMode: boolean;
    difficulty: string;
    refreshInterval: number;
  };
  summary: BenchmarkSummary;
  learning: LearningMetrics;
  timeSeries: TimeSeries;
  deliveries: DeliveryMetrics[];
}

// Agent mode info for display
export interface AgentModeInfo {
  id: AgentMode;
  name: string;
  description: string;
}

// Benchmark preset
export interface BenchmarkPreset {
  id: string;
  name: string;
  description: string;
  config: Partial<BenchmarkConfig>;
}

// WebSocket benchmark events
export type BenchmarkEventType =
  | 'benchmark_start'
  | 'benchmark_progress'
  | 'benchmark_complete'
  | 'delivery_start'
  | 'models_refreshing'
  | 'models_refreshed';

export interface BenchmarkStartPayload {
  mode: AgentMode;
  numDeliveries: number;
  difficulty: string;
}

export interface BenchmarkProgressPayload {
  completed: number;
  total: number;
  currentEfficiency: number;
  avgEfficiency: number;
}

export interface DeliveryStartPayload {
  deliveryId: number;
  recipient: string;
  business?: string;
  isRepeat: boolean;
  progress: string;
}
