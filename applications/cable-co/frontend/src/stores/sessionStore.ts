import { create } from 'zustand';
import type { AgentMode, CustomerScenario, AgentAction, PendingSuggestion, MemoryRecall, KnowledgeRule, ScenarioResult, MentalModel } from '../types.ts';

interface SessionState {
  // Connection
  connected: boolean;
  bankId: string | null;
  mode: AgentMode;
  totalScenarios: number;

  // Current scenario
  currentScenario: CustomerScenario | null;
  isProcessing: boolean;
  isThinking: boolean;

  // Activity
  actions: AgentAction[];
  memoryRecall: MemoryRecall | null;

  // Pending suggestion awaiting CSR decision
  pendingSuggestion: PendingSuggestion | null;

  // Knowledge
  knowledgeRules: KnowledgeRule[];

  // Metrics
  scenariosProcessed: number;
  history: ScenarioResult[];

  // Customer chat
  sentResponses: string[];
  // CSR messages to copilot
  csrMessages: { message: string; index: number }[];
  // Simulated customer replies
  customerReplies: string[];

  // Memory
  isStoringMemory: boolean;
  isRefreshingModels: boolean;
  mentalModels: MentalModel[];

  // Actions
  setConnected: (connected: boolean, bankId?: string, mode?: AgentMode, totalScenarios?: number) => void;
  setMode: (mode: AgentMode) => void;
  setScenario: (scenario: CustomerScenario) => void;
  setThinking: (thinking: boolean) => void;
  addAction: (action: AgentAction) => void;
  setMemoryRecall: (recall: MemoryRecall | null) => void;
  setPendingSuggestion: (suggestion: PendingSuggestion | null) => void;
  resolveSuggestion: (suggestionId: string, approved: boolean, feedback: string, result: string) => void;
  addKnowledgeRule: (rule: KnowledgeRule) => void;
  addCsrMessage: (message: string) => void;
  addSentResponse: (message: string) => void;
  addCustomerReply: (message: string) => void;
  setStoringMemory: (storing: boolean) => void;
  setRefreshingModels: (refreshing: boolean) => void;
  setMentalModels: (models: MentalModel[]) => void;
  resolveScenario: (result: ScenarioResult) => void;
  resetCurrent: () => void;
  resetAll: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  connected: false,
  bankId: null,
  mode: 'memory_on',
  totalScenarios: 8,

  currentScenario: null,
  isProcessing: false,
  isThinking: false,

  actions: [],
  memoryRecall: null,

  pendingSuggestion: null,

  knowledgeRules: [],

  scenariosProcessed: 0,
  history: [],

  sentResponses: [],
  csrMessages: [],
  customerReplies: [],

  isStoringMemory: false,
  isRefreshingModels: false,
  mentalModels: [],

  setConnected: (connected, bankId, mode, totalScenarios) => set((s) => ({
    connected,
    bankId: bankId ?? s.bankId,
    mode: mode ?? s.mode,
    totalScenarios: totalScenarios ?? s.totalScenarios,
  })),

  setMode: (mode) => set({ mode }),

  setScenario: (scenario) => set({
    currentScenario: scenario,
    isProcessing: true,
    isThinking: false,
    actions: [],
    memoryRecall: null,
    pendingSuggestion: null,
    sentResponses: [],
    csrMessages: [],
    customerReplies: [],
  }),

  setThinking: (thinking) => set({ isThinking: thinking }),

  addAction: (action) => set((s) => ({
    actions: [...s.actions, action],
    isThinking: false,
  })),

  setMemoryRecall: (recall) => set({ memoryRecall: recall }),

  setPendingSuggestion: (suggestion) => set({ pendingSuggestion: suggestion, isThinking: false }),

  resolveSuggestion: (suggestionId, approved, feedback, result) => set((s) => {
    if (s.pendingSuggestion?.suggestionId !== suggestionId) return {};
    const sug = s.pendingSuggestion;
    const action: AgentAction = {
      step: sug.step,
      toolName: sug.toolName,
      toolArgs: sug.toolArgs,
      toolResult: approved ? result : `CSR REJECTED: ${feedback}`,
      thinking: sug.reasoning || null,
      timing: 0,
      isAction: true,
      isLookup: false,
      rejected: !approved,
      rejectionFeedback: approved ? null : feedback,
    };
    return {
      pendingSuggestion: null,
      actions: [...s.actions, action],
    };
  }),

  addKnowledgeRule: (rule) => set((s) => {
    const exists = s.knowledgeRules.some((r) => r.feedback === rule.feedback);
    if (exists) return {};
    return { knowledgeRules: [...s.knowledgeRules, rule] };
  }),

  addCsrMessage: (message) => set((s) => ({
    csrMessages: [...s.csrMessages, { message, index: s.actions.length }],
  })),

  addSentResponse: (message) => set((s) => ({
    sentResponses: [...s.sentResponses, message],
  })),

  addCustomerReply: (message) => set((s) => ({
    customerReplies: [...s.customerReplies, message],
  })),

  setStoringMemory: (storing) => set({ isStoringMemory: storing }),

  setRefreshingModels: (refreshing) => set({ isRefreshingModels: refreshing }),

  setMentalModels: (models) => set({ mentalModels: models }),

  resolveScenario: (result) => set((s) => ({
    isProcessing: false,
    isThinking: false,
    pendingSuggestion: null,
    scenariosProcessed: s.scenariosProcessed + 1,
    history: [...s.history, result],
  })),

  resetCurrent: () => set({
    currentScenario: null,
    isProcessing: false,
    isThinking: false,
    actions: [],
    memoryRecall: null,
    pendingSuggestion: null,
    sentResponses: [],
    csrMessages: [],
    customerReplies: [],
  }),

  resetAll: () => set({
    currentScenario: null,
    isProcessing: false,
    isThinking: false,
    actions: [],
    memoryRecall: null,
    pendingSuggestion: null,
    sentResponses: [],
    csrMessages: [],
    customerReplies: [],
    knowledgeRules: [],
    scenariosProcessed: 0,
    history: [],
  }),
}));
