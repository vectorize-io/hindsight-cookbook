import { create } from 'zustand';
import type {
  Side,
  Package,
  DeliveryStatus,
  ActionEntry,
  DeliveryResult,
  ServerEvent,
  Mode,
  MemoryReflect
} from '../types';

type Difficulty = 'easy' | 'medium' | 'hard';

type HistoryEntry = DeliveryResult & { recipientName: string };

interface DifficultyStats {
  history: HistoryEntry[];
}

interface GameState {
  // Connection
  connected: boolean;
  clientId: string | null;

  // Agent state
  agentFloor: number;
  agentSide: Side;
  hasPackage: boolean;
  isThinking: boolean;
  thinkingText: string | null;
  isAnimating: boolean;

  // Current delivery
  currentPackage: Package | null;
  deliveryStatus: DeliveryStatus;
  deliverySteps: number;

  // Action log (current delivery only)
  actions: ActionEntry[];

  // Stats per difficulty
  difficulty: Difficulty;
  statsByDifficulty: Record<Difficulty, DifficultyStats>;

  // Computed stats for current difficulty (derived in selectors)
  // These are kept for backwards compatibility with components
  deliveriesCompleted: number;
  totalSteps: number;
  history: HistoryEntry[];

  // Memory
  bankId: string | null;
  memoryReflect: MemoryReflect | null;

  // Settings
  mode: Mode;
  includeBusiness: boolean;
  maxSteps: number | null;

  // Actions
  setConnected: (connected: boolean, clientId?: string, bankId?: string) => void;
  handleEvent: (event: ServerEvent) => void;
  startDelivery: (pkg: Package) => void;
  resetAgent: () => void;
  resetStats: () => void;
  resetHistory: () => void;
  resetAllHistory: () => void;
  setAgentPosition: (floor: number, side: Side) => void;
  setMode: (mode: Mode) => void;
  setIncludeBusiness: (value: boolean) => void;
  setMaxSteps: (value: number | null) => void;
  setAnimating: (value: boolean) => void;
  setBankId: (bankId: string) => void;
  setDifficulty: (difficulty: Difficulty) => void;
}

// Helper to compute derived stats from history
function computeStats(history: HistoryEntry[]) {
  return {
    deliveriesCompleted: history.filter(h => h.success).length,
    totalSteps: history.reduce((sum, h) => sum + h.steps, 0),
  };
}

const initialStatsByDifficulty: Record<Difficulty, DifficultyStats> = {
  easy: { history: [] },
  medium: { history: [] },
  hard: { history: [] },
};

export const useGameStore = create<GameState>((set, get) => ({
  // Initial state
  connected: false,
  clientId: null,
  agentFloor: 1,
  agentSide: 'front',
  hasPackage: false,
  isThinking: false,
  thinkingText: null,
  isAnimating: false,
  currentPackage: null,
  deliveryStatus: 'idle',
  deliverySteps: 0,
  actions: [],

  // Per-difficulty stats
  difficulty: 'easy',
  statsByDifficulty: { ...initialStatsByDifficulty },

  // Computed (will be updated when difficulty changes or history updates)
  deliveriesCompleted: 0,
  totalSteps: 0,
  history: [],

  bankId: null,
  memoryReflect: null,
  mode: 'ui',
  includeBusiness: false,
  maxSteps: 150,

  // Actions
  setConnected: (connected, clientId, bankId) => set({
    connected,
    clientId: clientId ?? get().clientId,
    bankId: bankId ?? get().bankId
  }),

  handleEvent: (event) => {
    const state = get();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const payload = event.payload as any;

    switch (event.type) {
      case 'connected':
        set({
          connected: true,
          clientId: payload?.clientId,
          bankId: payload?.bankId
        });
        break;

      case 'delivery_started':
        // Note: Don't reset agentFloor/agentSide here - let agent_action events update them
        // This avoids animation glitches when switching between difficulties
        // (e.g., medium mode uses 'building_a' instead of 'front')
        set({
          currentPackage: payload?.package,
          deliveryStatus: 'running',
          deliverySteps: 0,
          actions: [],
          hasPackage: true,
          memoryReflect: null,  // Reset memory reflect for new delivery
        });
        break;

      case 'memory_reflect':
        set({
          memoryReflect: payload as MemoryReflect,
        });
        break;

      case 'agent_thinking':
        set({ isThinking: true, thinkingText: payload?.thinking ?? null });
        break;

      case 'agent_action': {
        const actionPayload = payload as ActionEntry;
        set({
          isThinking: false,
          agentFloor: actionPayload.floor,
          agentSide: actionPayload.side as Side,
          deliverySteps: actionPayload.step,
          actions: [...state.actions, actionPayload],
        });
        break;
      }

      case 'memory_storing':
        set({ isThinking: true });
        break;

      case 'memory_stored':
        set({ isThinking: false });
        break;

      case 'delivery_success': {
        const steps = payload?.steps ?? state.deliverySteps;
        const newEntry: HistoryEntry = {
          package: state.currentPackage ?
            `${state.currentPackage.recipientName}${state.currentPackage.businessName ? ` @ ${state.currentPackage.businessName}` : ''}` :
            'Unknown',
          recipientName: state.currentPackage?.recipientName ?? 'Unknown',
          success: true,
          steps,
        };

        const currentDifficulty = state.difficulty;
        const updatedHistory = [...state.statsByDifficulty[currentDifficulty].history, newEntry];
        const stats = computeStats(updatedHistory);

        set({
          deliveryStatus: 'success',
          hasPackage: false,
          isThinking: false,
          thinkingText: null,
          statsByDifficulty: {
            ...state.statsByDifficulty,
            [currentDifficulty]: { history: updatedHistory },
          },
          // Update computed values
          history: updatedHistory,
          deliveriesCompleted: stats.deliveriesCompleted,
          totalSteps: stats.totalSteps,
        });
        break;
      }

      case 'delivery_failed':
      case 'step_limit_reached': {
        const steps = payload?.steps ?? state.deliverySteps;
        const newEntry: HistoryEntry = {
          package: state.currentPackage ?
            `${state.currentPackage.recipientName}${state.currentPackage.businessName ? ` @ ${state.currentPackage.businessName}` : ''}` :
            'Unknown',
          recipientName: state.currentPackage?.recipientName ?? 'Unknown',
          success: false,
          steps,
        };

        const currentDifficulty = state.difficulty;
        const updatedHistory = [...state.statsByDifficulty[currentDifficulty].history, newEntry];
        const stats = computeStats(updatedHistory);

        set({
          deliveryStatus: 'failed',
          hasPackage: false,
          isThinking: false,
          thinkingText: null,
          statsByDifficulty: {
            ...state.statsByDifficulty,
            [currentDifficulty]: { history: updatedHistory },
          },
          // Update computed values
          history: updatedHistory,
          deliveriesCompleted: stats.deliveriesCompleted,
          totalSteps: stats.totalSteps,
        });
        break;
      }

      case 'cancelled':
        set({
          deliveryStatus: 'cancelled',
          hasPackage: false,
          isThinking: false,
        });
        break;

      case 'error':
        console.error('WebSocket error:', payload);
        set({
          isThinking: false,
          deliveryStatus: 'failed',
        });
        break;
    }
  },

  startDelivery: (pkg) => set({
    currentPackage: pkg,
    deliveryStatus: 'running',
    deliverySteps: 0,
    actions: [],
    hasPackage: true,
    // Note: Don't reset agentFloor/agentSide - let agent_action events update them
  }),

  resetAgent: () => set({
    agentFloor: 1,
    agentSide: 'front',
    hasPackage: false,
    isThinking: false,
    currentPackage: null,
    deliveryStatus: 'idle',
    deliverySteps: 0,
    actions: [],
  }),

  resetStats: () => {
    const state = get();
    const currentDifficulty = state.difficulty;
    set({
      statsByDifficulty: {
        ...state.statsByDifficulty,
        [currentDifficulty]: { history: [] },
      },
      deliveriesCompleted: 0,
      totalSteps: 0,
      history: [],
    });
  },

  // Reset history for current difficulty only
  resetHistory: () => {
    const state = get();
    const currentDifficulty = state.difficulty;
    const initialSide = currentDifficulty === 'medium' ? 'building_a' : 'front';

    set({
      statsByDifficulty: {
        ...state.statsByDifficulty,
        [currentDifficulty]: { history: [] },
      },
      deliveriesCompleted: 0,
      totalSteps: 0,
      history: [],
      actions: [],
      deliveryStatus: 'idle',
      currentPackage: null,
      agentFloor: 1,
      agentSide: initialSide,
      hasPackage: false,
    });
  },

  // Reset history for ALL difficulties
  resetAllHistory: () => set({
    statsByDifficulty: { ...initialStatsByDifficulty },
    deliveriesCompleted: 0,
    totalSteps: 0,
    history: [],
    actions: [],
    deliveryStatus: 'idle',
    currentPackage: null,
    agentFloor: 1,
    agentSide: 'front',
    hasPackage: false,
  }),

  setAgentPosition: (floor, side) => set({
    agentFloor: floor,
    agentSide: side,
  }),

  setMode: (mode) => set({ mode }),
  setIncludeBusiness: (includeBusiness) => set({ includeBusiness }),
  setMaxSteps: (maxSteps) => set({ maxSteps }),
  setAnimating: (isAnimating) => set({ isAnimating }),
  setBankId: (bankId) => set({ bankId }),

  setDifficulty: (difficulty) => {
    const state = get();
    const difficultyHistory = state.statsByDifficulty[difficulty].history;
    const stats = computeStats(difficultyHistory);
    const initialSide = difficulty === 'medium' ? 'building_a' : 'front';

    set({
      difficulty,
      history: difficultyHistory,
      deliveriesCompleted: stats.deliveriesCompleted,
      totalSteps: stats.totalSteps,
      // Reset current delivery state when switching
      actions: [],
      deliveryStatus: 'idle',
      currentPackage: null,
      agentFloor: 1,
      agentSide: initialSide,
      hasPackage: false,
      memoryReflect: null,
    });
  },
}));
