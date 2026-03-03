import { create } from 'zustand';
import type { AgentMode, PipelineStage, Claim, AgentAction, MemoryInjection, ClaimResult, MentalModel } from '../types.ts';

interface ClaimsState {
  // Connection
  connected: boolean;
  bankId: string | null;
  mode: AgentMode;

  // Current claim
  currentClaim: Claim | null;
  currentStage: PipelineStage;
  isProcessing: boolean;
  isThinking: boolean;

  // Activity
  actions: AgentAction[];
  memoryInjection: MemoryInjection | null;

  // Metrics
  claimsProcessed: number;
  correctDecisions: number;
  totalSteps: number;
  totalRework: number;
  history: ClaimResult[];

  // Memory
  isStoringMemory: boolean;
  isRefreshingModels: boolean;
  mentalModels: MentalModel[];

  // Actions
  setConnected: (connected: boolean, bankId?: string, mode?: AgentMode) => void;
  setMode: (mode: AgentMode) => void;
  setClaim: (claim: Claim) => void;
  setStage: (stage: PipelineStage) => void;
  setThinking: (thinking: boolean) => void;
  addAction: (action: AgentAction) => void;
  setMemoryInjection: (injection: MemoryInjection | null) => void;
  setStoringMemory: (storing: boolean) => void;
  setRefreshingModels: (refreshing: boolean) => void;
  setMentalModels: (models: MentalModel[]) => void;
  resolveClaim: (result: ClaimResult) => void;
  resetCurrent: () => void;
}

export const useClaimsStore = create<ClaimsState>((set) => ({
  connected: false,
  bankId: null,
  mode: 'no_memory',

  currentClaim: null,
  currentStage: 'received',
  isProcessing: false,
  isThinking: false,

  actions: [],
  memoryInjection: null,

  claimsProcessed: 0,
  correctDecisions: 0,
  totalSteps: 0,
  totalRework: 0,
  history: [],

  isStoringMemory: false,
  isRefreshingModels: false,
  mentalModels: [],

  setConnected: (connected, bankId, mode) => set((s) => ({
    connected,
    bankId: bankId ?? s.bankId,
    mode: mode ?? s.mode,
  })),

  setMode: (mode) => set({ mode }),

  setClaim: (claim) => set({
    currentClaim: claim,
    currentStage: 'received',
    isProcessing: true,
    isThinking: false,
    actions: [],
    memoryInjection: null,
  }),

  setStage: (stage) => set({ currentStage: stage }),

  setThinking: (thinking) => set({ isThinking: thinking }),

  addAction: (action) => set((s) => ({
    actions: [...s.actions, action],
    isThinking: false,
  })),

  setMemoryInjection: (injection) => set({ memoryInjection: injection }),

  setStoringMemory: (storing) => set({ isStoringMemory: storing }),

  setRefreshingModels: (refreshing) => set({ isRefreshingModels: refreshing }),

  setMentalModels: (models) => set({ mentalModels: models }),

  resolveClaim: (result) => set((s) => ({
    isProcessing: false,
    isThinking: false,
    currentStage: 'resolved',
    claimsProcessed: s.claimsProcessed + 1,
    correctDecisions: s.correctDecisions + (result.correct ? 1 : 0),
    totalSteps: s.totalSteps + result.steps,
    totalRework: s.totalRework + result.reworkCount,
    history: [...s.history, result],
  })),

  resetCurrent: () => set({
    currentClaim: null,
    currentStage: 'received',
    isProcessing: false,
    isThinking: false,
    actions: [],
    memoryInjection: null,
  }),
}));
