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

  // Action log
  actions: ActionEntry[];

  // Stats
  deliveriesCompleted: number;
  totalSteps: number;
  history: (DeliveryResult & { recipientName: string })[];

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
  setMode: (mode: Mode) => void;
  setIncludeBusiness: (value: boolean) => void;
  setMaxSteps: (value: number | null) => void;
  setAnimating: (value: boolean) => void;
}

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
        set({
          deliveryStatus: 'success',
          hasPackage: false,
          isThinking: false,
          thinkingText: null,
          deliveriesCompleted: state.deliveriesCompleted + 1,
          totalSteps: state.totalSteps + steps,
          history: [...state.history, {
            package: state.currentPackage ?
              `${state.currentPackage.recipientName}${state.currentPackage.businessName ? ` @ ${state.currentPackage.businessName}` : ''}` :
              'Unknown',
            recipientName: state.currentPackage?.recipientName ?? 'Unknown',
            success: true,
            steps,
          }],
        });
        break;
      }

      case 'delivery_failed':
      case 'step_limit_reached': {
        const steps = payload?.steps ?? state.deliverySteps;
        set({
          deliveryStatus: 'failed',
          hasPackage: false,
          isThinking: false,
          thinkingText: null,
          totalSteps: state.totalSteps + steps,
          history: [...state.history, {
            package: state.currentPackage ?
              `${state.currentPackage.recipientName}${state.currentPackage.businessName ? ` @ ${state.currentPackage.businessName}` : ''}` :
              'Unknown',
            recipientName: state.currentPackage?.recipientName ?? 'Unknown',
            success: false,
            steps,
          }],
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

  resetStats: () => set({
    deliveriesCompleted: 0,
    totalSteps: 0,
    history: [],
  }),

  resetHistory: () => set({
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

  setMode: (mode) => set({ mode }),
  setIncludeBusiness: (includeBusiness) => set({ includeBusiness }),
  setMaxSteps: (maxSteps) => set({ maxSteps }),
  setAnimating: (isAnimating) => set({ isAnimating }),
}));
