import { useEffect, useState, useRef, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useToast } from './hooks/useToast';
import { ToastContainer } from './components/ToastContainer';
import { useGameStore } from './stores/gameStore';
import { PhaserGame } from './game/PhaserGame';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { Employee } from './types';

// Demo config type
interface DemoConfig {
  systemPrompt: string;
  llmModel: string;
  hindsight: {
    apiUrl: string;
    bankId: string;
    method: string;
    queryTemplate: string;
    budget: string | number;
    mission: string;
    background: string;
  };
  tools: { name: string; description: string }[];
}

// Building info type
interface BuildingInfo {
  floors: number;
  businesses: {
    name: string;
    floor: number;
    side: string;
    employees: { name: string; role: string }[];
  }[];
  isMultiBuilding?: boolean;
  difficulty?: string;
  // Hard mode city grid
  isCityGrid?: boolean;
  cityBuildings?: {
    name: string;
    row: number;
    col: number;
    floors: {
      floor: number;
      name: string;
      employees: { name: string; role: string }[];
    }[];
  }[];
  gridRows?: number;
  gridCols?: number;
}

function ActionLogEntry({ action, expanded, onToggle }: {
  action: {
    step: number;
    toolName: string;
    toolArgs: Record<string, unknown>;
    toolResult: string;
    thinking?: string;
  };
  expanded: boolean;
  onToggle: () => void;
}) {
  const getToolIcon = (name: string) => {
    const icons: Record<string, string> = {
      'go_up': '⬆️',
      'go_down': '⬇️',
      'go_to_front': '➡️',
      'go_to_back': '⬅️',
      'get_employee_list': '📋',
      'deliver_package': '📦',
      'check_current_location': '📍',
    };
    return icons[name] || '🔧';
  };

  return (
    <div
      className="bg-slate-700/50 rounded-lg p-3 cursor-pointer hover:bg-slate-700 transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        <span className="text-lg">{getToolIcon(action.toolName)}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-green-400 font-medium">{action.toolName}</span>
            {Object.keys(action.toolArgs).length > 0 && (
              <span className="text-slate-500 text-xs">
                ({Object.entries(action.toolArgs).map(([k, v]) => `${k}=${v}`).join(', ')})
              </span>
            )}
          </div>
          {!expanded && (
            <div className="text-slate-400 text-xs truncate mt-0.5">
              {action.toolResult}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-slate-500 text-xs font-mono">#{action.step}</span>
          <span className="text-slate-400 text-xs">{expanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2 text-sm">
          {action.thinking && (
            <div className="bg-slate-800 rounded p-2">
              <div className="text-slate-500 text-xs uppercase mb-1">Thinking</div>
              <div className="text-slate-300 text-xs italic">{action.thinking}</div>
            </div>
          )}
          <div className="bg-slate-800 rounded p-2">
            <div className="text-slate-500 text-xs uppercase mb-1">Result</div>
            <div className="text-green-300 text-xs font-mono whitespace-pre-wrap">{action.toolResult}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const { toasts, showError, dismiss: dismissToast } = useToast();
  const { connected, isConnecting, startDelivery, cancelDelivery, resetMemory } = useWebSocket();
  const {
    agentFloor,
    agentSide,
    isThinking,
    isAnimating,
    isStoringMemory,
    thinkingText,
    deliveryStatus,
    deliverySteps,
    currentPackage,
    actions,
    deliveriesCompleted,
    totalSteps,
    history,
    includeBusiness,
    maxSteps,
    setIncludeBusiness,
    setMaxSteps,
    resetHistory,
    memoryReflect,
    bankId: storeBankId,
    setBankId: setStoreBankId,
    setDifficulty: setStoreDifficulty,
    setAgentPosition,
    // Hard mode grid state
    agentGridRow,
    agentGridCol,
    agentCurrentBuilding,
    setAgentGridPosition,
  } = useGameStore();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedRecipient, setSelectedRecipient] = useState<string>('');
  const [expandedAction, setExpandedAction] = useState<number | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);
  const [buildingInfo, setBuildingInfo] = useState<BuildingInfo | null>(null);
  const [showDemoSettings, setShowDemoSettings] = useState(false);
  const [showAvailableTools, setShowAvailableTools] = useState(false);
  const [showBuildingLayout, setShowBuildingLayout] = useState(false);
  const [expandedCityBuildings, setExpandedCityBuildings] = useState<Set<string>>(new Set());

  // Difficulty state
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('easy');

  // Bank management state
  const [currentBankId, setCurrentBankId] = useState<string>('');
  const [showBankMenu, setShowBankMenu] = useState(false);
  const [bankInput, setBankInput] = useState('');
  const [bankCopied, setBankCopied] = useState(false);
  const [bankHistory, setBankHistory] = useState<string[]>([]);

  // Mental models state (reflections from Hindsight API)
  interface BasedOnItem {
    fact_type?: string;
    content?: string;
    quote?: string;
    memory_id?: string;
    timestamp?: string;
  }
  interface MentalModel {
    id: string;
    name: string;
    source_query?: string;
    content?: string;  // Main reflection content
    description?: string;
    summary?: string;
    subtype?: string;
    created_at?: string;
    last_refreshed_at?: string;
    reflect_response?: {
      answer?: string;
      based_on?: BasedOnItem[];
    };
  }
  const [mentalModels, setMentalModels] = useState<MentalModel[]>([]);
  const [mentalModelsLoading, setMentalModelsLoading] = useState(false);
  const [mentalModelsWaitingForRefresh, setMentalModelsWaitingForRefresh] = useState(false);
  const [mentalModelsExpanded, setMentalModelsExpanded] = useState(false);
  const [expandedModelId, setExpandedModelId] = useState<string | null>(null);
  const [newPinnedModelName, setNewPinnedModelName] = useState('');
  const [fetchInterval, setFetchInterval] = useState(5);  // Auto-fetch every N deliveries (0 = off)
  const [deliveriesSinceFetch, setDeliveriesSinceFetch] = useState(0);

  // View mode state (UI vs Training)
  const [viewMode, setViewMode] = useState<'ui' | 'training'>('ui');

  // UI mode loop state
  const [loopDeliveries, setLoopDeliveries] = useState(false);
  const [loopTarget, setLoopTarget] = useState(5);
  const [loopCompleted, setLoopCompleted] = useState(0);
  const loopAbortRef = useRef(false);
  const loopStartHistoryRef = useRef(0);

  // Training mode state
  const [trainingTarget, setTrainingTarget] = useState(10);
  const [trainingRunning, setTrainingRunning] = useState(false);
  const [trainingCompleted, setTrainingCompleted] = useState(0);
  const trainingAbortRef = useRef(false);
  const trainingStartHistoryRef = useRef(0);  // History length when training started
  const lastProcessedHistoryRef = useRef(0);  // Last history length we processed

  // Fetch employees, demo config, and building info on mount
  useEffect(() => {
    fetch('/api/building/employees')
      .then(res => res.json())
      .then(data => setEmployees(data.employees))
      .catch(console.error);

    fetch('/api/demo-config?app=demo')
      .then(res => res.json())
      .then(data => setDemoConfig(data))
      .catch(console.error);

    fetch('/api/building')
      .then(res => res.json())
      .then(data => setBuildingInfo(data))
      .catch(console.error);

    // Get current difficulty, bank ID, and history (app=demo for this frontend)
    fetch('/api/difficulty?app=demo')
      .then(res => res.json())
      .then(data => {
        const diff = data.difficulty as 'easy' | 'medium' | 'hard';
        setDifficulty(diff);
        setCurrentBankId(data.bankId || '');
        // Sync store difficulty (sets correct initial position)
        setStoreDifficulty(diff);
        setStoreBankId(data.bankId || '');

        // Fetch mental models on startup using the correct difficulty
        fetch(`/api/memory/mental-models?app=demo&difficulty=${diff}`)
          .then(res => res.json())
          .then(modelsData => setMentalModels(sortModels(modelsData.models || [])))
          .catch(console.error);

        // Fetch bank history for the correct difficulty
        fetch(`/api/memory/bank/history?app=demo&difficulty=${diff}`)
          .then(res => res.json())
          .then(data => setBankHistory(data.history || []))
          .catch(console.error);
      })
      .catch(console.error);
  }, []);

  // Refresh employees and building for current difficulty
  const refreshBuildingData = useCallback(async () => {
    try {
      const [empRes, buildingRes, configRes] = await Promise.all([
        fetch('/api/building/employees'),
        fetch('/api/building'),
        fetch('/api/demo-config?app=demo'),
      ]);
      const [empData, buildingData, configData] = await Promise.all([
        empRes.json(),
        buildingRes.json(),
        configRes.json(),
      ]);
      setEmployees(empData.employees || []);
      setBuildingInfo(buildingData);
      setDemoConfig(configData);
      setSelectedRecipient(''); // Reset selection since employees changed
    } catch (err) {
      console.error('Failed to refresh building data:', err);
    }
  }, []);

  // Refresh bank history (accepts optional override to avoid stale closure after difficulty change)
  const refreshBankHistory = useCallback(async (overrideDifficulty?: string) => {
    try {
      const diff = overrideDifficulty || difficulty;
      const res = await fetch(`/api/memory/bank/history?app=demo&difficulty=${diff}`);
      const data = await res.json();
      setBankHistory(data.history || []);
    } catch (err) {
      console.error('Failed to fetch bank history:', err);
    }
  }, [difficulty]);

  // Sort mental models alphabetically by name
  const sortModels = (models: MentalModel[]) =>
    [...models].sort((a, b) => a.name.localeCompare(b.name));

  // Fetch mental models for the current bank, waiting for any pending operations first
  const fetchMentalModels = useCallback(async () => {
    try {
      setMentalModelsLoading(true);

      const checkStats = async () => {
        const res = await fetch(`/api/memory/stats?app=demo&difficulty=${difficulty}`);
        const data = await res.json();
        return {
          ops: data.stats?.pending_operations ?? 0,
          cons: data.stats?.pending_consolidation ?? 0,
        };
      };

      let { ops, cons } = await checkStats();

      if (ops > 0 || cons > 0) {
        setMentalModelsWaitingForRefresh(true);
        const startTime = Date.now();
        const timeout = 120_000; // 2 min max wait

        while (Date.now() - startTime < timeout) {
          await new Promise(r => setTimeout(r, 2000));
          ({ ops, cons } = await checkStats());
          if (ops === 0 && cons === 0) break;
        }

        setMentalModelsWaitingForRefresh(false);
      }

      const res = await fetch(`/api/memory/mental-models?app=demo&difficulty=${difficulty}`);
      const data = await res.json();
      setMentalModels(sortModels(data.models || []));
    } catch (err) {
      console.error('Failed to fetch mental models:', err);
    } finally {
      setMentalModelsLoading(false);
      setMentalModelsWaitingForRefresh(false);
    }
  }, [difficulty]);

  // Fetch single mental model with full details
  const fetchMentalModelDetails = useCallback(async (modelId: string) => {
    try {
      const res = await fetch(`/api/memory/mental-models/${modelId}?app=demo&difficulty=${difficulty}`);
      const data = await res.json();
      if (data.model) {
        // Update the model in the list with full details
        setMentalModels(prev => prev.map(m =>
          m.id === modelId ? { ...m, ...data.model } : m
        ));
      }
    } catch (err) {
      console.error('Failed to fetch mental model details:', err);
    }
  }, [difficulty]);

  // Toggle model expansion and fetch details if needed
  const toggleModelExpansion = useCallback((modelId: string) => {
    if (expandedModelId === modelId) {
      setExpandedModelId(null);
    } else {
      setExpandedModelId(modelId);
      // Fetch full details when expanding
      fetchMentalModelDetails(modelId);
    }
  }, [expandedModelId, fetchMentalModelDetails]);

  // Create a pinned mental model
  const createPinnedModel = useCallback(async (name: string) => {
    if (!name.trim()) return;
    try {
      const res = await fetch(`/api/memory/mental-models/pinned?app=demo&difficulty=${difficulty}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (res.ok) {
        setNewPinnedModelName('');
        fetchMentalModels();
      }
    } catch (err) {
      console.error('Failed to create pinned model:', err);
      showError('Failed to create pinned model');
    }
  }, [difficulty, fetchMentalModels, showError]);

  // Delete a mental model
  const deleteMentalModel = useCallback(async (modelId: string) => {
    try {
      const res = await fetch(`/api/memory/mental-models/${modelId}?app=demo&difficulty=${difficulty}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setMentalModels(prev => prev.filter(m => m.id !== modelId));
        if (expandedModelId === modelId) {
          setExpandedModelId(null);
        }
      }
    } catch (err) {
      console.error('Failed to delete mental model:', err);
      showError('Failed to delete mental model');
    }
  }, [difficulty, expandedModelId, showError]);

  // Sync currentBankId when gameStore's bankId changes (e.g., after reset_memory)
  useEffect(() => {
    if (storeBankId && storeBankId !== currentBankId) {
      setCurrentBankId(storeBankId);
      // Also refresh bank history
      refreshBankHistory();
    }
  }, [storeBankId, currentBankId, refreshBankHistory]);

  // Auto-fetch mental models every N deliveries, triggered when retain completes (memory_stored)
  const wasStoringForFetchRef = useRef(false);
  useEffect(() => {
    if (isStoringMemory) {
      wasStoringForFetchRef.current = true;
    } else if (wasStoringForFetchRef.current) {
      wasStoringForFetchRef.current = false;
      // Retain just finished — count this delivery
      setDeliveriesSinceFetch(prev => {
        const next = prev + 1;
        if (fetchInterval > 0 && next >= fetchInterval) {
          fetchMentalModels();
          return 0;
        }
        return next;
      });
    }
  }, [isStoringMemory, fetchInterval, fetchMentalModels]);

  // Change difficulty
  const changeDifficulty = useCallback(async (newDifficulty: 'easy' | 'medium' | 'hard') => {
    if (newDifficulty === difficulty) return;
    try {
      const res = await fetch('/api/difficulty', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ difficulty: newDifficulty }),
      });
      const data = await res.json();
      setDifficulty(newDifficulty);
      setCurrentBankId(data.bankId || '');
      // Also update gameStore so the sync effect doesn't overwrite with stale value
      setStoreBankId(data.bankId || '');
      // Update store difficulty (preserves history, resets current delivery state)
      setStoreDifficulty(newDifficulty);
      // Refresh building data for new difficulty
      await refreshBuildingData();
      // Refresh bank history for new difficulty (pass explicitly to avoid stale closure)
      await refreshBankHistory(newDifficulty);
      // Fetch mental models for the new difficulty's bank
      // Note: fetchMentalModels uses `difficulty` from closure which is stale here,
      // so fetch directly with the new difficulty
      try {
        const mmRes = await fetch(`/api/memory/mental-models?app=demo&difficulty=${newDifficulty}`);
        const mmData = await mmRes.json();
        setMentalModels(sortModels(mmData.models || []));
      } catch (mmErr) {
        console.error('Failed to fetch mental models for new difficulty:', mmErr);
      }
    } catch (err) {
      console.error('Failed to change difficulty:', err);
      showError('Failed to change difficulty');
    }
  }, [difficulty, refreshBuildingData, refreshBankHistory, setStoreBankId, setStoreDifficulty, showError]);

  // Bank management functions
  const copyBankId = useCallback(() => {
    navigator.clipboard.writeText(currentBankId);
    setBankCopied(true);
    setTimeout(() => setBankCopied(false), 2000);
  }, [currentBankId]);

  const generateNewBank = useCallback(async () => {
    try {
      const res = await fetch(`/api/memory/bank/new?app=demo&difficulty=${difficulty}`, { method: 'POST' });
      if (!res.ok) {
        showError(`Failed to generate new bank (${res.status})`);
        return;
      }
      const data = await res.json();
      setCurrentBankId(data.bankId);
      setStoreBankId(data.bankId);
      setShowBankMenu(false);
      refreshBankHistory();
      fetchMentalModels();
      // Also update demo config
      if (demoConfig) {
        setDemoConfig({ ...demoConfig, hindsight: { ...demoConfig.hindsight, bankId: data.bankId } });
      }
    } catch (err) {
      console.error('Failed to generate new bank:', err);
      showError('Failed to generate new bank');
    }
  }, [difficulty, demoConfig, refreshBankHistory, fetchMentalModels, setStoreBankId, showError]);

  const switchToBank = useCallback(async (bankId: string) => {
    try {
      const res = await fetch(`/api/memory/bank?app=demo&difficulty=${difficulty}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bankId }),
      });
      const data = await res.json();
      setCurrentBankId(data.bankId);
      setStoreBankId(data.bankId);
      setShowBankMenu(false);
      refreshBankHistory();
      fetchMentalModels();
      // Also update demo config
      if (demoConfig) {
        setDemoConfig({ ...demoConfig, hindsight: { ...demoConfig.hindsight, bankId: data.bankId } });
      }
    } catch (err) {
      console.error('Failed to switch bank:', err);
      showError('Failed to switch bank');
    }
  }, [difficulty, demoConfig, refreshBankHistory, fetchMentalModels, setStoreBankId, showError]);

  const setExistingBank = useCallback(async () => {
    if (!bankInput.trim()) return;
    await switchToBank(bankInput.trim());
    setBankInput('');
  }, [bankInput, switchToBank]);

  // Auto-expand latest action when it changes
  useEffect(() => {
    if (actions.length > 0) {
      setExpandedAction(actions.length - 1);
    }
  }, [actions.length]);

  // Filter out employees at the agent's starting location (trivial 0-step deliveries)
  const getEligibleEmployees = useCallback(() => {
    const eligible = employees.filter(e => {
      if (difficulty === 'easy') return !(e.floor === 1 && e.side === 'front');
      if (difficulty === 'medium') return !(e.floor === 1 && e.side === 'building_a');
      return true; // hard mode: agent starts on street, all are eligible
    });
    return eligible.length > 0 ? eligible : employees;
  }, [employees, difficulty]);

  // Start a random delivery for training mode (with reflect hindsight)
  const startRandomTrainingDelivery = useCallback(() => {
    if (employees.length > 0 && connected) {
      const eligible = getEligibleEmployees();
      const randomEmployee = eligible[Math.floor(Math.random() * eligible.length)];
      const hindsightSettings = {
        inject: true,
        reflect: true,
        store: true,
        query: `Where does ${randomEmployee.name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries.`,
      };
      startDelivery(randomEmployee.name, includeBusiness, maxSteps, undefined, hindsightSettings);
    }
  }, [employees, connected, startDelivery, includeBusiness, maxSteps, getEligibleEmployees]);

  // Training mode: auto-start next delivery when previous completes
  useEffect(() => {
    if (!trainingRunning || viewMode !== 'training') return;
    if (trainingAbortRef.current) {
      setTrainingRunning(false);
      return;
    }

    // Check if a NEW delivery just completed (not already processed)
    if (history.length > lastProcessedHistoryRef.current) {
      lastProcessedHistoryRef.current = history.length;

      const completedInSession = history.length - trainingStartHistoryRef.current;
      setTrainingCompleted(completedInSession);

      // Check if we've reached the target
      if (completedInSession >= trainingTarget) {
        setTrainingRunning(false);
        return;
      }

      // Start next delivery after a short delay (wait for memory to finish storing)
      setTimeout(() => {
        if (!trainingAbortRef.current && trainingRunning && !isStoringMemory) {
          startRandomTrainingDelivery();
        }
      }, 100);  // Minimal delay - just enough for state to settle
    }
  }, [history.length, trainingRunning, trainingTarget, viewMode, startRandomTrainingDelivery, isStoringMemory]);

  // Training mode: continue when memory storage completes
  const wasStoringRef = useRef(false);
  useEffect(() => {
    // Track when storage completes
    if (isStoringMemory) {
      wasStoringRef.current = true;
    } else if (wasStoringRef.current) {
      // Storage just completed
      wasStoringRef.current = false;

      // If training is running and we're not already delivering, start next
      if (trainingRunning && deliveryStatus !== 'running' && !trainingAbortRef.current) {
        const completedInSession = history.length - trainingStartHistoryRef.current;
        if (completedInSession < trainingTarget) {
          startRandomTrainingDelivery();
        }
      }
    }
  }, [isStoringMemory, trainingRunning, deliveryStatus, history.length, trainingTarget, startRandomTrainingDelivery]);

  // Start training
  const handleStartTraining = useCallback(() => {
    trainingAbortRef.current = false;
    trainingStartHistoryRef.current = history.length;
    lastProcessedHistoryRef.current = history.length;
    setTrainingCompleted(0);
    setTrainingRunning(true);
    startRandomTrainingDelivery();
  }, [history.length, startRandomTrainingDelivery]);

  // Stop training
  const handleStopTraining = useCallback(() => {
    trainingAbortRef.current = true;
    setTrainingRunning(false);
    cancelDelivery();
  }, [cancelDelivery]);

  // UI mode loop: start random delivery
  const startLoopDelivery = useCallback(() => {
    if (employees.length > 0 && connected && !loopAbortRef.current) {
      const eligible = getEligibleEmployees();
      const randomEmployee = eligible[Math.floor(Math.random() * eligible.length)];
      setSelectedRecipient(randomEmployee.name);
      const hindsightSettings = {
        inject: true,
        reflect: true,
        store: true,
        query: `Where does ${randomEmployee.name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries.`,
      };
      startDelivery(randomEmployee.name, includeBusiness, maxSteps, undefined, hindsightSettings);
    }
  }, [employees, connected, startDelivery, includeBusiness, maxSteps, getEligibleEmployees]);

  // UI mode loop: auto-start next delivery when BOTH storing and animations complete
  const loopWasStoringRef = useRef(false);
  const loopWasAnimatingRef = useRef(false);
  const loopDeliveryCompleteRef = useRef(false);

  // Track delivery completion
  useEffect(() => {
    if (!loopDeliveries || viewMode !== 'ui') return;

    // Mark delivery as complete when we see success/failed status
    if (deliveryStatus === 'success' || deliveryStatus === 'failed') {
      loopDeliveryCompleteRef.current = true;
    }
  }, [loopDeliveries, viewMode, deliveryStatus]);

  // Track storing and animation states, start next delivery when both complete
  useEffect(() => {
    if (!loopDeliveries || viewMode !== 'ui') return;
    if (loopAbortRef.current) {
      setLoopDeliveries(false);
      return;
    }

    // Track state transitions
    if (isStoringMemory) {
      loopWasStoringRef.current = true;
    }
    if (isAnimating) {
      loopWasAnimatingRef.current = true;
    }

    // Check if delivery completed and both storing and animations are done
    // If storing/animating was never triggered, consider it done (e.g., on failed deliveries)
    const storingDone = !loopWasStoringRef.current || !isStoringMemory;
    const animatingDone = !loopWasAnimatingRef.current || !isAnimating;
    const deliveryDone = loopDeliveryCompleteRef.current;

    if (deliveryDone && storingDone && animatingDone) {
      // Reset tracking refs for next delivery
      loopWasStoringRef.current = false;
      loopWasAnimatingRef.current = false;
      loopDeliveryCompleteRef.current = false;

      // Update completed count
      const completedInLoop = history.length - loopStartHistoryRef.current;
      setLoopCompleted(completedInLoop);

      // Check if we've reached the target
      if (completedInLoop >= loopTarget) {
        setLoopDeliveries(false);
        return;
      }

      // Start next delivery after a brief pause
      if (!loopAbortRef.current) {
        setTimeout(() => {
          startLoopDelivery();
        }, 500);
      }
    }
  }, [loopDeliveries, viewMode, isStoringMemory, isAnimating, startLoopDelivery, history.length, loopTarget]);

  // Start loop mode
  const handleStartLoop = useCallback(() => {
    loopAbortRef.current = false;
    loopStartHistoryRef.current = history.length;
    setLoopCompleted(0);
    setLoopDeliveries(true);
    startLoopDelivery();
  }, [startLoopDelivery, history.length]);

  // Stop loop mode
  const handleStopLoop = useCallback(() => {
    loopAbortRef.current = true;
    setLoopDeliveries(false);
    cancelDelivery();
  }, [cancelDelivery]);

  // Hindsight settings for reflect mode
  const getHindsightSettings = (recipientName: string) => ({
    inject: true,
    reflect: true,
    store: true,
    query: `Where does ${recipientName} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries.`,
  });

  const handleStartDelivery = () => {
    if (selectedRecipient) {
      startDelivery(selectedRecipient, includeBusiness, maxSteps, undefined, getHindsightSettings(selectedRecipient));
    }
  };

  const handleRandomDelivery = () => {
    if (employees.length > 0) {
      const eligible = getEligibleEmployees();
      const randomEmployee = eligible[Math.floor(Math.random() * eligible.length)];
      setSelectedRecipient(randomEmployee.name);
      startDelivery(randomEmployee.name, includeBusiness, maxSteps, undefined, getHindsightSettings(randomEmployee.name));
    }
  };

  const handleResetMemory = async () => {
    if (confirm('This will clear all agent memories and delivery history. Continue?')) {
      resetMemory();
      resetHistory();
      // WebSocket will send 'connected' event with new bankId - store will update automatically
      // Fetch from REST API as fallback after longer delay to ensure backend processed the reset
      setTimeout(async () => {
        try {
          const res = await fetch(`/api/memory/bank?app=demo&difficulty=${difficulty}`);
          const data = await res.json();
          if (data.bankId && data.bankId !== currentBankId) {
            console.log('Reset: updating bank ID from REST API:', data.bankId);
            setCurrentBankId(data.bankId);
            setStoreBankId(data.bankId);
          }
          refreshBankHistory();
          fetchMentalModels();
        } catch (err) {
          console.error('Failed to refresh bank ID after reset:', err);
          showError('Failed to reset memory');
        }
      }, 1000);  // Longer delay to ensure backend processes reset + bank creation
    }
  };

  // Chart data - steps per delivery
  const chartData = history.map((h, i) => ({
    delivery: i + 1,
    steps: h.steps,
    success: h.success,
  }));

  const avgSteps = history.length > 0
    ? (history.reduce((sum, h) => sum + h.steps, 0) / history.length).toFixed(1)
    : '-';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100">
      {/* Header */}
      <header className="bg-slate-900/50 border-b border-slate-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-blue-400 font-mono">
              DELIVERY AGENT DEMO
            </h1>
            <p className="text-slate-500 text-sm">
              AI agent learning with Hindsight memory
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                connected ? 'bg-green-500 shadow-lg shadow-green-500/50' :
                isConnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="text-sm text-slate-400">
                {connected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
              </span>
            </div>

            {/* Bank ID with controls */}
            <div className="relative">
              <div className="flex items-center gap-1">
                <code className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">
                  {currentBankId || 'Loading...'}
                </code>
                <button
                  onClick={copyBankId}
                  className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
                  title="Copy bank ID"
                >
                  {bankCopied ? (
                    <span className="text-green-400 text-xs">✓</span>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  )}
                </button>
                <button
                  onClick={() => setShowBankMenu(!showBankMenu)}
                  className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
                  title="Bank options"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>

              {/* Bank menu dropdown */}
              {showBankMenu && (
                <div className="absolute right-0 mt-2 w-72 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 p-3 space-y-3">
                  <button
                    onClick={generateNewBank}
                    className="w-full text-left px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 rounded-md transition-colors flex items-center gap-2"
                  >
                    <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Generate New Bank
                  </button>

                  {/* Bank History */}
                  {bankHistory.length > 0 && (
                    <div className="border-t border-slate-700 pt-3">
                      <label className="block text-xs text-slate-500 mb-2">Recent Banks</label>
                      <div className="space-y-1 max-h-32 overflow-y-auto">
                        {bankHistory.map((bankId) => (
                          <button
                            key={bankId}
                            onClick={() => switchToBank(bankId)}
                            className={`w-full text-left px-2 py-1.5 text-xs font-mono rounded transition-colors flex items-center justify-between ${
                              bankId === currentBankId
                                ? 'bg-blue-600/30 text-blue-300 cursor-default'
                                : 'text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                            }`}
                            disabled={bankId === currentBankId}
                          >
                            <span className="truncate">{bankId}</span>
                            {bankId === currentBankId && (
                              <span className="text-[10px] text-blue-400 ml-2">current</span>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="border-t border-slate-700 pt-3">
                    <label className="block text-xs text-slate-500 mb-1">Use Existing Bank</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={bankInput}
                        onChange={(e) => setBankInput(e.target.value)}
                        placeholder="demo-xxxxxxxx"
                        className="flex-1 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-xs text-white focus:border-blue-500 focus:outline-none"
                        onKeyDown={(e) => e.key === 'Enter' && setExistingBank()}
                      />
                      <button
                        onClick={setExistingBank}
                        disabled={!bankInput.trim()}
                        className="px-2 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white text-xs rounded transition-colors"
                      >
                        Set
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 max-w-7xl mx-auto">
        {/* Mode and Difficulty Selection */}
        <div className="mb-6 flex flex-wrap items-center gap-6">
          {/* View Mode Tabs */}
          <div className="flex gap-2 p-1 bg-slate-800/50 rounded-lg">
            <button
              onClick={() => setViewMode('ui')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                viewMode === 'ui'
                  ? 'bg-gradient-to-r from-green-600 to-green-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              UI Mode
            </button>
            <button
              onClick={() => setViewMode('training')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                viewMode === 'training'
                  ? 'bg-gradient-to-r from-yellow-600 to-orange-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Training Mode
            </button>
          </div>

          {/* Difficulty Selector */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 uppercase tracking-wider">Difficulty</span>
            <div className="flex gap-1 p-1 bg-slate-800/50 rounded-lg">
              {(['easy', 'medium', 'hard'] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => changeDifficulty(d)}
                  disabled={deliveryStatus === 'running'}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    difficulty === d
                      ? d === 'easy'
                        ? 'bg-green-600 text-white'
                        : d === 'medium'
                        ? 'bg-yellow-600 text-white'
                        : 'bg-red-600 text-white'
                      : 'text-slate-400 hover:text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed'
                  }`}
                >
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
            <span className="text-xs text-slate-500">
              {difficulty === 'easy' ? '3 floors' : difficulty === 'medium' ? '3 buildings' : '7 floors'}
            </span>
          </div>
        </div>

        {/* Demo Settings Collapsible */}
        <div className="mb-6">
          <button
            onClick={() => setShowDemoSettings(!showDemoSettings)}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-300 transition-colors"
          >
            <span className={`transition-transform ${showDemoSettings ? 'rotate-90' : ''}`}>
              ▶
            </span>
            <span>Demo Settings</span>
          </button>

          {showDemoSettings && demoConfig && (
            <div className="mt-3 bg-slate-800/50 rounded-xl p-4 border border-slate-700 space-y-4">
              {/* Agent Model */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Agent Model</h3>
                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                  <code className="text-blue-400 text-sm font-mono">{demoConfig.llmModel}</code>
                </div>
              </div>

              {/* System Prompt */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">System Prompt</h3>
                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                  <code className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                    {demoConfig.systemPrompt}
                  </code>
                </div>
              </div>

              {/* Hindsight Config */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Hindsight Memory</h3>
                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Method</span>
                    <span className="text-purple-400">{demoConfig.hindsight.method}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">API URL</span>
                    <code className="text-purple-400 font-mono text-xs">{demoConfig.hindsight.apiUrl}</code>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Bank ID</span>
                    <code className="text-purple-400 font-mono text-xs">{demoConfig.hindsight.bankId}</code>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Budget</span>
                    <span className="text-purple-400">{demoConfig.hindsight.budget}</span>
                  </div>
                  <div className="text-sm pt-2 border-t border-slate-700">
                    <span className="text-slate-400">Mission</span>
                    <code className="block text-purple-400 font-mono text-xs mt-1 bg-slate-800/50 p-2 rounded whitespace-pre-wrap">
                      {demoConfig.hindsight.mission}
                    </code>
                  </div>
                  <div className="text-sm pt-2 border-t border-slate-700">
                    <span className="text-slate-400">Bank Background <span className="text-orange-400 text-[10px]">(deprecated)</span></span>
                    <code className="block text-purple-400 font-mono text-xs mt-1 bg-slate-800/50 p-2 rounded">
                      {demoConfig.hindsight.background}
                    </code>
                  </div>
                  <div className="text-sm pt-2 border-t border-slate-700">
                    <span className="text-slate-400">Query Template</span>
                    <code className="block text-purple-400 font-mono text-xs mt-1 bg-slate-800/50 p-2 rounded">
                      {demoConfig.hindsight.queryTemplate}
                    </code>
                  </div>
                </div>
              </div>

              {/* Available Tools - Collapsible */}
              <div>
                <button
                  onClick={() => setShowAvailableTools(!showAvailableTools)}
                  className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-wider mb-2 hover:text-slate-400 transition-colors"
                >
                  <span className={`transition-transform text-[10px] ${showAvailableTools ? 'rotate-90' : ''}`}>
                    ▶
                  </span>
                  <span>Available Tools</span>
                </button>

                {showAvailableTools && (
                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {demoConfig.tools.map(tool => (
                        <div key={tool.name} className="flex items-start gap-2 text-sm">
                          <code className="text-yellow-400 font-mono shrink-0">{tool.name}</code>
                          <span className="text-slate-500">-</span>
                          <span className="text-slate-400">{tool.description}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Building Layout - Collapsible */}
              <div>
                <button
                  onClick={() => setShowBuildingLayout(!showBuildingLayout)}
                  className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-wider mb-2 hover:text-slate-400 transition-colors"
                >
                  <span className={`transition-transform text-[10px] ${showBuildingLayout ? 'rotate-90' : ''}`}>
                    ▶
                  </span>
                  <span>{buildingInfo?.isCityGrid ? 'City Layout' : 'Building Layout'}</span>
                </button>

                {showBuildingLayout && buildingInfo && (
                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-4">
                    {/* City Grid Layout (hard mode) */}
                    {buildingInfo.isCityGrid && buildingInfo.cityBuildings ? (
                      <>
                        <div className="text-sm text-slate-400 mb-2">
                          12 buildings • {buildingInfo.cityBuildings.reduce((acc, b) => acc + b.floors.reduce((facc, f) => facc + f.employees.length, 0), 0)} employees
                          <span className="ml-2 text-orange-400">(City Grid)</span>
                        </div>
                        {/* Group buildings by row */}
                        {[0, 1, 2].map((rowNum) => {
                          const rowBuildings = buildingInfo.cityBuildings!.filter(b => b.row === rowNum);
                          return (
                            <div key={rowNum} className="space-y-2">
                              <div className="text-xs text-slate-500 uppercase">Row {rowNum + 1}</div>
                              <div className="grid grid-cols-2 gap-2">
                                {rowBuildings.map((building) => {
                                  const isExpanded = expandedCityBuildings.has(building.name);
                                  const toggleExpand = () => {
                                    const newSet = new Set(expandedCityBuildings);
                                    if (isExpanded) {
                                      newSet.delete(building.name);
                                    } else {
                                      newSet.add(building.name);
                                    }
                                    setExpandedCityBuildings(newSet);
                                  };
                                  return (
                                    <div key={building.name} className="border border-slate-700 rounded-lg overflow-hidden">
                                      <button
                                        onClick={toggleExpand}
                                        className="w-full bg-slate-700/50 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition-colors flex items-center justify-between"
                                      >
                                        <span>{building.name}</span>
                                        <span className={`transition-transform text-[10px] ${isExpanded ? 'rotate-90' : ''}`}>
                                          ▶
                                        </span>
                                      </button>
                                      {isExpanded && (
                                        <div className="p-2 space-y-2">
                                          {building.floors.map((floor) => (
                                            <div key={floor.floor} className="border-l-2 border-cyan-500/30 pl-2">
                                              <div className="text-xs text-slate-500">Floor {floor.floor}: <span className="text-cyan-400">{floor.name}</span></div>
                                              <div className="mt-0.5 space-y-0.5">
                                                {floor.employees.map(emp => (
                                                  <div key={emp.name} className="text-xs text-slate-400 pl-2">
                                                    <span className="text-slate-300">{emp.name}</span>
                                                    <span className="text-slate-500"> • {emp.role}</span>
                                                  </div>
                                                ))}
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </>
                    ) : (
                      <>
                        <div className="text-sm text-slate-400 mb-2">
                          {buildingInfo.floors} floors • {buildingInfo.businesses.length} businesses • {buildingInfo.businesses.reduce((acc, b) => acc + b.employees.length, 0)} employees
                          {buildingInfo.isMultiBuilding && <span className="ml-2 text-yellow-400">(3 buildings)</span>}
                        </div>

                        {/* Render floors from top to bottom */}
                        {[...Array(buildingInfo.floors)].map((_, i) => {
                          const floorNum = buildingInfo.floors - i;
                          const floorBusinesses = buildingInfo.businesses.filter(b => b.floor === floorNum);

                          // Multi-building layout (medium difficulty)
                          if (buildingInfo.isMultiBuilding) {
                            const buildingABiz = floorBusinesses.find(b => b.side === 'building_a');
                            const buildingBBiz = floorBusinesses.find(b => b.side === 'building_b');
                            const buildingCBiz = floorBusinesses.find(b => b.side === 'building_c');

                            return (
                              <div key={floorNum} className="border border-slate-700 rounded-lg overflow-hidden">
                                <div className="bg-slate-700/50 px-3 py-1.5 text-xs font-medium text-slate-300">
                                  Floor {floorNum}
                                </div>
                                <div className="grid grid-cols-3 divide-x divide-slate-700">
                                  {/* Building A */}
                                  <div className="p-2">
                                    <div className="text-xs text-slate-500 uppercase mb-1">Building A</div>
                                    {buildingABiz ? (
                                      <div>
                                        <div className="text-sm font-medium text-cyan-400">{buildingABiz.name}</div>
                                        <div className="mt-1 space-y-0.5">
                                          {buildingABiz.employees.map(emp => (
                                            <div key={emp.name} className="text-xs text-slate-400">
                                              <span className="text-slate-300">{emp.name}</span>
                                              <span className="text-slate-500"> • {emp.role}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="text-xs text-slate-500 italic">Empty</div>
                                    )}
                                  </div>
                                  {/* Building B */}
                                  <div className="p-2">
                                    <div className="text-xs text-slate-500 uppercase mb-1">Building B</div>
                                    {buildingBBiz ? (
                                      <div>
                                        <div className="text-sm font-medium text-cyan-400">{buildingBBiz.name}</div>
                                        <div className="mt-1 space-y-0.5">
                                          {buildingBBiz.employees.map(emp => (
                                            <div key={emp.name} className="text-xs text-slate-400">
                                              <span className="text-slate-300">{emp.name}</span>
                                              <span className="text-slate-500"> • {emp.role}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="text-xs text-slate-500 italic">Empty</div>
                                    )}
                                  </div>
                                  {/* Building C */}
                                  <div className="p-2">
                                    <div className="text-xs text-slate-500 uppercase mb-1">Building C</div>
                                    {buildingCBiz ? (
                                      <div>
                                        <div className="text-sm font-medium text-cyan-400">{buildingCBiz.name}</div>
                                        <div className="mt-1 space-y-0.5">
                                          {buildingCBiz.employees.map(emp => (
                                            <div key={emp.name} className="text-xs text-slate-400">
                                              <span className="text-slate-300">{emp.name}</span>
                                              <span className="text-slate-500"> • {emp.role}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="text-xs text-slate-500 italic">Empty</div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          }

                          // Single building layout (easy difficulty)
                          const frontBiz = floorBusinesses.find(b => b.side === 'front');
                          const backBiz = floorBusinesses.find(b => b.side === 'back');

                          return (
                            <div key={floorNum} className="border border-slate-700 rounded-lg overflow-hidden">
                              <div className="bg-slate-700/50 px-3 py-1.5 text-xs font-medium text-slate-300">
                                Floor {floorNum}
                              </div>
                              <div className="grid grid-cols-2 divide-x divide-slate-700">
                                {/* Front side */}
                                <div className="p-2">
                                  <div className="text-xs text-slate-500 uppercase mb-1">Front</div>
                                  {frontBiz ? (
                                    <div>
                                      <div className="text-sm font-medium text-cyan-400">{frontBiz.name}</div>
                                      <div className="mt-1 space-y-0.5">
                                        {frontBiz.employees.map(emp => (
                                          <div key={emp.name} className="text-xs text-slate-400">
                                            <span className="text-slate-300">{emp.name}</span>
                                            <span className="text-slate-500"> • {emp.role}</span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="text-xs text-slate-500 italic">Empty</div>
                                  )}
                                </div>
                                {/* Back side */}
                                <div className="p-2">
                                  <div className="text-xs text-slate-500 uppercase mb-1">Back</div>
                                  {backBiz ? (
                                    <div>
                                      <div className="text-sm font-medium text-cyan-400">{backBiz.name}</div>
                                      <div className="mt-1 space-y-0.5">
                                        {backBiz.employees.map(emp => (
                                          <div key={emp.name} className="text-xs text-slate-400">
                                            <span className="text-slate-300">{emp.name}</span>
                                            <span className="text-slate-500"> • {emp.role}</span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="text-xs text-slate-500 italic">Empty</div>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* UI Mode Content */}
        {viewMode === 'ui' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Game View */}
          <div className="lg:col-span-2 space-y-4">
            {/* Game Canvas */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Building View</h2>
                {currentPackage && (
                  <div className="flex items-center gap-2 bg-blue-500/20 text-blue-400 px-3 py-1 rounded-full text-sm">
                    <span>📦</span>
                    <span>{currentPackage.recipientName}</span>
                    {currentPackage.businessName && (
                      <span className="text-blue-300">@ {currentPackage.businessName}</span>
                    )}
                  </div>
                )}
              </div>

              <PhaserGame
                floor={agentFloor}
                side={agentSide}
                isThinking={(isThinking || isStoringMemory) && !isAnimating}
                packageText={currentPackage ? `${currentPackage.recipientName}${currentPackage.businessName ? ` @ ${currentPackage.businessName}` : ''}` : ''}
                deliverySuccess={deliveryStatus === 'success'}
                deliveryFailed={deliveryStatus === 'failed'}
                deliveryCancelled={deliveryStatus === 'cancelled'}
                lastActionTool={actions.length > 0 ? actions[actions.length - 1].toolName : undefined}
                difficulty={difficulty}
                // Hard mode grid props
                gridRow={agentGridRow}
                gridCol={agentGridCol}
                currentBuilding={agentCurrentBuilding}
              />

              {/* FOR ANIMATION TESTING - Animation test buttons
              <div className="mt-4 p-3 bg-yellow-900/20 border border-yellow-600/30 rounded-lg">
                <div className="text-xs text-yellow-500 uppercase tracking-wider mb-2">Animation Testing</div>

                {difficulty === 'hard' && !agentCurrentBuilding && (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-400 mb-1">City Grid (3x7) - Buildings at even cols, roads at odd cols</div>
                    <div className="flex flex-wrap gap-2">
                      {(() => {
                        const buildings: Record<string, string> = {
                          '0_0': 'Tech Corp', '0_2': 'City Bank', '0_4': 'Law Office', '0_6': 'Medical',
                          '1_0': 'Real Estate', '1_2': 'News Studio', '1_4': 'Accounting', '1_6': 'Insurance Co',
                          '2_0': 'Marketing', '2_2': 'Consulting', '2_4': 'Engineering', '2_6': 'Data Center',
                        };
                        const isAtBuilding = agentGridCol % 2 === 0;
                        const currentBuilding = buildings[`${agentGridRow}_${agentGridCol}`];
                        return (
                          <>
                            <button onClick={() => setAgentGridPosition(agentGridRow - 1, agentGridCol, null)} disabled={agentGridRow === 0 || isAtBuilding} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">⬆️ North</button>
                            <button onClick={() => setAgentGridPosition(agentGridRow + 1, agentGridCol, null)} disabled={agentGridRow === 2 || isAtBuilding} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">⬇️ South</button>
                            <button onClick={() => setAgentGridPosition(agentGridRow, agentGridCol - 1, null)} disabled={agentGridCol === 0} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">⬅️ West</button>
                            <button onClick={() => setAgentGridPosition(agentGridRow, agentGridCol + 1, null)} disabled={agentGridCol === 6} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">➡️ East</button>
                            <span className="text-slate-500 text-xs self-center mx-2">|</span>
                            <button onClick={() => { if (currentBuilding) { setAgentGridPosition(agentGridRow, agentGridCol, currentBuilding); } }} disabled={!isAtBuilding} className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">🏢 Enter Building</button>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                )}

                {difficulty === 'hard' && agentCurrentBuilding && (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-400 mb-1">Inside: {agentCurrentBuilding}</div>
                    <div className="flex flex-wrap gap-2">
                      <button onClick={() => setAgentPosition(Math.min(agentFloor + 1, 4), agentSide)} disabled={agentFloor === 4} className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">⬆️ Go Up</button>
                      <button onClick={() => setAgentPosition(Math.max(agentFloor - 1, 1), agentSide)} disabled={agentFloor === 1} className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs rounded">⬇️ Go Down</button>
                      <span className="text-slate-500 text-xs self-center mx-2">|</span>
                      <button onClick={() => setAgentGridPosition(agentGridRow, agentGridCol, null)} className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded">🚪 Exit Building</button>
                    </div>
                  </div>
                )}

                {difficulty !== 'hard' && (
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => setAgentPosition(Math.min(agentFloor + 1, difficulty === 'medium' ? 4 : 3), agentSide)} className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded">⬆️ Go Up</button>
                    <button onClick={() => setAgentPosition(Math.max(agentFloor - 1, 1), agentSide)} className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded">⬇️ Go Down</button>
                    {difficulty === 'medium' ? (
                      <>
                        <button onClick={() => setAgentPosition(agentFloor, 'building_a')} className={`px-3 py-1.5 text-xs rounded ${agentSide === 'building_a' ? 'bg-green-600' : 'bg-slate-600 hover:bg-slate-500'} text-white`}>Building A</button>
                        <button onClick={() => setAgentPosition(agentFloor, 'building_b')} className={`px-3 py-1.5 text-xs rounded ${agentSide === 'building_b' ? 'bg-green-600' : 'bg-slate-600 hover:bg-slate-500'} text-white`}>Building B</button>
                        <button onClick={() => setAgentPosition(agentFloor, 'building_c')} className={`px-3 py-1.5 text-xs rounded ${agentSide === 'building_c' ? 'bg-green-600' : 'bg-slate-600 hover:bg-slate-500'} text-white`}>Building C</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => setAgentPosition(agentFloor, 'front')} className={`px-3 py-1.5 text-xs rounded ${agentSide === 'front' ? 'bg-green-600' : 'bg-slate-600 hover:bg-slate-500'} text-white`}>Front</button>
                        <button onClick={() => setAgentPosition(agentFloor, 'back')} className={`px-3 py-1.5 text-xs rounded ${agentSide === 'back' ? 'bg-green-600' : 'bg-slate-600 hover:bg-slate-500'} text-white`}>Back</button>
                      </>
                    )}
                    <span className="text-slate-500 text-xs self-center mx-2">|</span>
                    <button onClick={() => setAgentPosition(1, difficulty === 'medium' ? 'building_a' : 'front')} className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded">Reset F1</button>
                  </div>
                )}
              </div>
              END ANIMATION TESTING */}

              {/* Status Bar */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-700">
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-slate-500">
                    Position: <span className="text-white font-mono">F{agentFloor} {agentSide}</span>
                  </span>
                  {deliveryStatus === 'running' && (
                    <span className="text-blue-400">
                      Step: <span className="font-mono">{deliverySteps}</span>
                    </span>
                  )}
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium uppercase tracking-wider ${
                  deliveryStatus === 'idle' ? 'bg-slate-600/50 text-slate-400' :
                  deliveryStatus === 'running' ? 'bg-blue-600/50 text-blue-300' :
                  deliveryStatus === 'success' ? 'bg-green-600/50 text-green-300' :
                  'bg-red-600/50 text-red-300'
                }`}>
                  {deliveryStatus}
                </span>
              </div>

              {/* Thinking Indicator */}
              {isThinking && !isAnimating && (
                <div className="mt-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-yellow-400 text-sm">
                    <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
                    <span className="font-medium">Agent is thinking...</span>
                  </div>
                  {thinkingText && (
                    <p className="text-yellow-300/80 text-xs mt-2 italic line-clamp-2">
                      {thinkingText}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Learning Curve Chart */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Learning Curve</h2>
                <span className="text-xs text-slate-500">
                  Avg: <span className="text-white font-mono">{avgSteps}</span> steps/delivery
                </span>
              </div>
              {history.length < 2 ? (
                <div className="h-32 flex items-center justify-center text-slate-500 text-sm">
                  Complete at least 2 deliveries to see learning progress
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={chartData}>
                    <XAxis
                      dataKey="delivery"
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                      domain={[0, 'auto']}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="steps"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={(props) => {
                        const { cx, cy, payload } = props;
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={4}
                            fill={payload.success ? '#3b82f6' : '#ef4444'}
                            stroke={payload.success ? '#3b82f6' : '#ef4444'}
                            strokeWidth={0}
                          />
                        );
                      }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Mental Models */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 relative">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-slate-300">Mental Models</h2>
                <span className="text-xs text-purple-400">
                  {mentalModels.length} models
                </span>
              </div>

              {/* Action buttons */}
              <div className="flex gap-2 flex-wrap mb-3">
                <button
                  onClick={fetchMentalModels}
                  disabled={mentalModelsLoading || isStoringMemory}
                  className="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-500 rounded text-white disabled:opacity-50 transition-colors"
                >
                  {mentalModelsWaitingForRefresh || mentalModelsLoading ? 'Refreshing...' : 'Refresh'}
                </button>
                <div className="flex items-center gap-1 ml-auto text-xs">
                  <span className="text-slate-500">Auto-fetch:</span>
                  <select
                    value={fetchInterval}
                    onChange={(e) => {
                      setFetchInterval(parseInt(e.target.value));
                      setDeliveriesSinceFetch(0);
                    }}
                    className="px-1.5 py-1 bg-slate-700 border border-slate-600 rounded text-slate-300 text-xs"
                  >
                    <option value={0}>Off</option>
                    <option value={1}>1</option>
                    <option value={3}>3</option>
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                  </select>
                  {fetchInterval > 0 && (
                    <span className="text-slate-500">
                      ({deliveriesSinceFetch}/{fetchInterval})
                    </span>
                  )}
                </div>
              </div>

              {/* Create pinned model */}
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={newPinnedModelName}
                  onChange={(e) => setNewPinnedModelName(e.target.value)}
                  placeholder="Pin a topic to track..."
                  className="flex-1 px-2 py-1.5 text-xs bg-slate-700 border border-slate-600 rounded text-slate-300 placeholder-slate-500"
                  onKeyDown={(e) => e.key === 'Enter' && createPinnedModel(newPinnedModelName)}
                />
                <button
                  onClick={() => createPinnedModel(newPinnedModelName)}
                  disabled={!newPinnedModelName.trim()}
                  className="px-3 py-1.5 text-xs bg-green-600 hover:bg-green-500 rounded text-white disabled:opacity-50 transition-colors"
                >
                  + Pin
                </button>
              </div>

              {/* Models list */}
              {mentalModels.length > 0 ? (
                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {mentalModels.map((model, idx) => (
                    <div key={model.id || idx} className="bg-slate-700/50 rounded border border-slate-600 overflow-hidden">
                      {/* Model header - clickable to expand */}
                      <button
                        onClick={() => toggleModelExpansion(model.id)}
                        className="w-full p-2 text-left hover:bg-slate-600/30 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={`transition-transform text-[10px] text-slate-500 ${expandedModelId === model.id ? 'rotate-90' : ''}`}>
                              ▶
                            </span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              model.subtype === 'structural' ? 'text-blue-400 bg-blue-900/30' :
                              model.subtype === 'emergent' ? 'text-green-400 bg-green-900/30' :
                              model.subtype === 'pinned' ? 'text-yellow-400 bg-yellow-900/30' :
                              'text-purple-400 bg-purple-900/30'
                            }`}>
                              {model.subtype || 'model'}
                            </span>
                            <span className="text-sm text-slate-300 font-medium truncate">{model.name}</span>
                          </div>
                          {model.reflect_response?.based_on && (
                            <span className="text-[10px] text-slate-500 shrink-0">
                              {model.reflect_response.based_on.length} facts
                            </span>
                          )}
                        </div>
                        {model.source_query && (
                          <p className="text-xs text-slate-500 mt-1 ml-5 line-clamp-1 italic">"{model.source_query}"</p>
                        )}
                      </button>

                      {/* Expanded content */}
                      {expandedModelId === model.id && (
                        <div className="border-t border-slate-600 p-2 space-y-2 bg-slate-800/50">
                          {model.content ? (
                            <div className="space-y-3">
                              {/* Main content */}
                              <div className="bg-slate-700/50 rounded p-3 border border-slate-600">
                                <p className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">{model.content}</p>
                              </div>

                              {/* Based on facts */}
                              {model.reflect_response?.based_on && model.reflect_response.based_on.length > 0 && (
                                <div className="space-y-1">
                                  <span className="text-[10px] text-slate-500 uppercase">Based on {model.reflect_response.based_on.length} memories:</span>
                                  <div className="space-y-1 max-h-32 overflow-y-auto">
                                    {model.reflect_response.based_on.slice(0, 5).map((item, idx) => (
                                      <div key={idx} className="text-[10px] text-slate-500 pl-2 border-l border-slate-600 flex items-start gap-2">
                                        <span className={`shrink-0 px-1 py-0.5 rounded ${
                                          item.fact_type === 'world' ? 'bg-blue-900/30 text-blue-400' :
                                          item.fact_type === 'experience' ? 'bg-green-900/30 text-green-400' :
                                          'bg-purple-900/30 text-purple-400'
                                        }`}>
                                          {item.fact_type || 'fact'}
                                        </span>
                                        <span className="italic">"{(item.content || item.quote)?.slice(0, 80)}{(item.content || item.quote)?.length > 80 ? '...' : ''}"</span>
                                      </div>
                                    ))}
                                    {model.reflect_response.based_on.length > 5 && (
                                      <span className="text-[10px] text-slate-600 pl-2">+{model.reflect_response.based_on.length - 5} more</span>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* Timestamps */}
                              {model.last_refreshed_at && (
                                <div className="text-[10px] text-slate-600">
                                  Refreshed: {new Date(model.last_refreshed_at).toLocaleString()}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-xs text-slate-500 text-center py-2">
                              No content yet. Click "Refresh" to generate.
                            </div>
                          )}
                          {/* Delete button */}
                          <button
                            onClick={(e) => { e.stopPropagation(); deleteMentalModel(model.id); }}
                            className="w-full mt-2 px-2 py-1 text-xs bg-red-900/30 hover:bg-red-800/50 text-red-400 rounded transition-colors"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500 text-center py-4">
                  No mental models yet. Run deliveries and click "Refresh" to synthesize.
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Controls & Logs */}
          <div className="space-y-4">
            {/* Controls */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <h2 className="text-lg font-semibold text-slate-300 mb-4">Controls</h2>

              {/* Recipient Select */}
              <div className="mb-4">
                <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                  Recipient
                </label>
                <select
                  value={selectedRecipient}
                  onChange={(e) => setSelectedRecipient(e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2.5 text-white focus:border-blue-500 focus:outline-none transition-colors"
                  disabled={deliveryStatus === 'running'}
                >
                  <option value="">Choose a recipient...</option>
                  {employees.map(emp => (
                    <option key={emp.name} value={emp.name}>
                      {emp.building ? `${emp.building} ` : ''}F{emp.floor} {emp.side} | {emp.business} | {emp.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Options */}
              <div className="mb-4 space-y-3">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={includeBusiness}
                    onChange={(e) => setIncludeBusiness(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                  />
                  <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                    Include business name in prompt
                  </span>
                </label>

                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Max Steps (optional)
                  </label>
                  <input
                    type="number"
                    value={maxSteps ?? ''}
                    onChange={(e) => setMaxSteps(e.target.value ? parseInt(e.target.value) : null)}
                    placeholder="No limit"
                    min={1}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleStartDelivery}
                  disabled={!connected || !selectedRecipient || deliveryStatus === 'running' || isStoringMemory || loopDeliveries}
                  className="flex-1 bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-green-500/20 disabled:shadow-none"
                >
                  {loopDeliveries ? 'Looping...' : deliveryStatus === 'running' ? 'Running...' : (isStoringMemory && !isAnimating) ? 'Storing...' : 'Start Delivery'}
                </button>
                <button
                  onClick={cancelDelivery}
                  disabled={deliveryStatus !== 'running'}
                  className="bg-red-600/80 hover:bg-red-600 disabled:bg-slate-600/50 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-colors"
                >
                  Stop
                </button>
              </div>

              {/* Random Delivery Button */}
              <button
                onClick={handleRandomDelivery}
                disabled={!connected || deliveryStatus === 'running' || employees.length === 0 || isStoringMemory || loopDeliveries}
                className="w-full mt-2 bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-500 hover:to-blue-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-purple-500/20 disabled:shadow-none"
              >
                Random Delivery
              </button>

              {/* Loop Deliveries */}
              <div className="mt-3 p-3 bg-slate-700/30 rounded-lg border border-slate-600">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm text-slate-400">Loop</span>
                  <input
                    type="number"
                    value={loopTarget}
                    onChange={(e) => setLoopTarget(Math.max(1, parseInt(e.target.value) || 1))}
                    disabled={loopDeliveries}
                    min={1}
                    className="w-16 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-white text-sm text-center disabled:opacity-50"
                  />
                  <span className="text-sm text-slate-400">deliveries</span>
                  {loopDeliveries && (
                    <span className="text-xs text-cyan-400 ml-auto">({loopCompleted}/{loopTarget})</span>
                  )}
                </div>
                <button
                  onClick={loopDeliveries ? handleStopLoop : handleStartLoop}
                  disabled={!connected || employees.length === 0}
                  className={`w-full px-3 py-2 rounded-lg font-medium text-sm transition-all ${
                    loopDeliveries
                      ? 'bg-gradient-to-r from-orange-600 to-red-500 hover:from-orange-500 hover:to-red-400'
                      : 'bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed'
                  }`}
                >
                  {loopDeliveries ? 'Stop Loop' : 'Start Loop'}
                </button>
              </div>

              {/* Reset Memory */}
              <button
                onClick={handleResetMemory}
                disabled={deliveryStatus === 'running' || loopDeliveries}
                className="w-full mt-3 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-400 hover:text-slate-300 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Reset Memory & History
              </button>
            </div>

            {/* Stats */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <h2 className="text-lg font-semibold text-slate-300 mb-4">Statistics</h2>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                  <div className="text-2xl font-bold text-green-400">{deliveriesCompleted}</div>
                  <div className="text-xs text-slate-500 mt-1">Deliveries</div>
                </div>
                <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                  <div className="text-2xl font-bold text-blue-400">{totalSteps}</div>
                  <div className="text-xs text-slate-500 mt-1">Total Steps</div>
                </div>
                <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-400">
                    {history.length > 0 ? Math.round(history.filter(h => h.success).length / history.length * 100) : 0}%
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Success</div>
                </div>
              </div>
            </div>

            {/* Hindsight Memory */}
            {memoryReflect && (
              <div className="bg-purple-900/20 rounded-xl p-4 border border-purple-500/30">
                <h2 className="text-lg font-semibold text-purple-300 mb-3">Hindsight Memory</h2>
                <div className="space-y-3">
                  {/* Query */}
                  <div>
                    <div className="text-purple-400 text-xs uppercase mb-1">Query</div>
                    <div className="text-purple-200 text-sm font-mono bg-purple-950/50 rounded p-2">
                      {memoryReflect.query}
                    </div>
                  </div>
                  {/* Synthesized Memory */}
                  <div>
                    <div className="text-purple-400 text-xs uppercase mb-1">Synthesized Memory</div>
                    {memoryReflect.text ? (
                      <div className="text-purple-100 text-sm whitespace-pre-wrap bg-purple-950/50 rounded p-2 max-h-40 overflow-y-auto">
                        {memoryReflect.text}
                      </div>
                    ) : memoryReflect.error ? (
                      <div className="text-red-400 text-sm bg-red-950/50 rounded p-2">
                        Error: {memoryReflect.error}
                      </div>
                    ) : (
                      <div className="text-slate-400 text-sm italic bg-purple-950/50 rounded p-2">
                        No relevant memories found
                      </div>
                    )}
                  </div>
                  {/* Timing */}
                  {memoryReflect.timing && (
                    <div className="text-purple-400/60 text-xs">
                      Retrieved in {(memoryReflect.timing * 1000).toFixed(0)}ms
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Action Log */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Action Log</h2>
                {actions.length > 0 && (
                  <span className="text-xs text-slate-500">{actions.length} actions</span>
                )}
              </div>
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {actions.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 text-sm">
                    <div className="text-2xl mb-2">📦</div>
                    Start a delivery to see agent actions
                  </div>
                ) : (
                  [...actions].reverse().map((action, i) => (
                    <ActionLogEntry
                      key={actions.length - 1 - i}
                      action={action}
                      expanded={expandedAction === actions.length - 1 - i}
                      onToggle={() => setExpandedAction(
                        expandedAction === actions.length - 1 - i ? null : actions.length - 1 - i
                      )}
                    />
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
        )}

        {/* Training Mode Content */}
        {viewMode === 'training' && (
          <div className="space-y-6">
            {/* Training Controls */}
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <h2 className="text-xl font-semibold text-slate-300 mb-4">Training Configuration</h2>
              <p className="text-slate-500 text-sm mb-6">
                Automatically run random deliveries to train the agent's memory.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Total Deliveries
                  </label>
                  <input
                    type="number"
                    value={trainingTarget}
                    onChange={(e) => setTrainingTarget(parseInt(e.target.value) || 1)}
                    min={1}
                    max={100}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-yellow-500 focus:outline-none"
                    disabled={trainingRunning}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Max Steps per Delivery
                  </label>
                  <input
                    type="number"
                    value={maxSteps ?? 100}
                    onChange={(e) => setMaxSteps(parseInt(e.target.value) || 100)}
                    min={1}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-yellow-500 focus:outline-none"
                    disabled={trainingRunning}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Auto-Fetch Models
                  </label>
                  <div className="flex items-center gap-2">
                    <select
                      value={fetchInterval}
                      onChange={(e) => {
                        setFetchInterval(parseInt(e.target.value));
                        setDeliveriesSinceFetch(0);
                      }}
                      className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-yellow-500 focus:outline-none"
                      disabled={trainingRunning}
                    >
                      <option value={0}>Off</option>
                      <option value={1}>Every 1</option>
                      <option value={3}>Every 3</option>
                      <option value={5}>Every 5</option>
                      <option value={10}>Every 10</option>
                    </select>
                    {fetchInterval > 0 && (
                      <span className="text-sm text-slate-400 whitespace-nowrap">
                        ({deliveriesSinceFetch}/{fetchInterval})
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-3 cursor-pointer group pb-2">
                    <input
                      type="checkbox"
                      checked={includeBusiness}
                      onChange={(e) => setIncludeBusiness(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-yellow-500 focus:ring-yellow-500 focus:ring-offset-0"
                      disabled={trainingRunning}
                    />
                    <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                      Include business name
                    </span>
                  </label>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleStartTraining}
                  disabled={!connected || trainingRunning || employees.length === 0}
                  className="flex-1 bg-gradient-to-r from-yellow-600 to-orange-500 hover:from-yellow-500 hover:to-orange-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-medium text-lg transition-all shadow-lg shadow-yellow-500/20 disabled:shadow-none"
                >
                  {trainingRunning ? 'Training...' : `Start Training (${trainingTarget} deliveries)`}
                </button>
                <button
                  onClick={handleStopTraining}
                  disabled={!trainingRunning}
                  className="bg-red-600/80 hover:bg-red-600 disabled:bg-slate-600/50 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-medium transition-colors"
                >
                  Stop
                </button>
              </div>

              {/* Progress */}
              {(trainingRunning || trainingCompleted > 0) && (
                <div className="mt-6">
                  <div className="flex justify-between text-sm text-slate-400 mb-2">
                    <span>Progress</span>
                    <span>{trainingCompleted} / {trainingTarget} deliveries</span>
                  </div>
                  <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-yellow-500 to-orange-500 transition-all duration-300"
                      style={{ width: `${Math.min(100, (trainingCompleted / trainingTarget) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Current Delivery Status */}
            {trainingRunning && (
              <div className="bg-slate-800/50 rounded-xl p-4 border border-yellow-500/30">
                <div className="flex items-center gap-4">
                  <div className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse" />
                  <div>
                    <div className="text-yellow-400 font-medium">
                      Delivery #{trainingCompleted + 1} in progress
                    </div>
                    {currentPackage && (
                      <div className="text-slate-400 text-sm">
                        Delivering to: {currentPackage.recipientName}
                        {currentPackage.businessName && ` @ ${currentPackage.businessName}`}
                      </div>
                    )}
                    <div className="text-slate-500 text-xs mt-1">
                      Step {deliverySteps} • Position: F{agentFloor} {agentSide}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Learning Curve Chart */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Learning Curve</h2>
                {history.length > 0 && (
                  <div className="flex items-center gap-4 text-sm text-slate-400">
                    <span>
                      Avg: <span className="text-white font-mono">{(history.reduce((sum, h) => sum + h.steps, 0) / history.length).toFixed(1)}</span> steps
                    </span>
                    <span>
                      Success: <span className="text-green-400 font-mono">{Math.round(history.filter(h => h.success).length / history.length * 100)}%</span>
                    </span>
                  </div>
                )}
              </div>
              {history.length < 2 ? (
                <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
                  Complete at least 2 deliveries to see learning progress
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={chartData}>
                    <XAxis
                      dataKey="delivery"
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                      domain={[0, 'auto']}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="steps"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      dot={(props) => {
                        const { cx, cy, payload } = props;
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={4}
                            fill={payload.success ? '#f59e0b' : '#ef4444'}
                            stroke={payload.success ? '#f59e0b' : '#ef4444'}
                            strokeWidth={0}
                          />
                        );
                      }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Reset Button */}
            <div className="flex justify-center">
              <button
                onClick={() => {
                  if (confirm('This will clear all agent memories and delivery history. Continue?')) {
                    resetMemory();
                    resetHistory();
                    trainingStartHistoryRef.current = 0;
                    lastProcessedHistoryRef.current = 0;
                    setTrainingCompleted(0);
                  }
                }}
                disabled={trainingRunning}
                className="bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-400 hover:text-slate-300 disabled:cursor-not-allowed px-6 py-2 rounded-lg text-sm transition-colors"
              >
                Reset Memory & History
              </button>
            </div>
          </div>
        )}
      </main>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default App;
