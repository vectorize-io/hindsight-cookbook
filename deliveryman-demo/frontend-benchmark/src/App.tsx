import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useGameStore } from './stores/gameStore';
import { PhaserGame } from './game/PhaserGame';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, BarChart, Bar, Legend } from 'recharts';
import type { Employee } from './types';

// Demo config type
interface DemoConfig {
  systemPrompt: string;
  llmModel: string;
  hindsight: {
    apiUrl: string;
    storeConversations: boolean;
    injectMemories: boolean;
    useReflect: boolean;
  };
  tools: { name: string; description: string }[];
  difficulty?: string;
}

// Difficulty type
type Difficulty = 'easy' | 'medium' | 'hard';

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
  isCityGrid?: boolean;
  difficulty?: string;
  cityBuildings?: {
    name: string;
    row: number;
    col: number;
    floors: { floor: number; name: string; employees: { name: string; role: string }[] }[];
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
    memoryInjection?: { injected: boolean; count: number; context?: string; bankId?: string; query?: string; error?: string | null };
  };
  expanded: boolean;
  onToggle: () => void;
}) {
  const [memoryExpanded, setMemoryExpanded] = useState(false);
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
          {action.memoryInjection && (
            <div className={`border rounded ${action.memoryInjection.count > 0 ? 'bg-purple-900/30 border-purple-500/30' : action.memoryInjection.error ? 'bg-red-900/30 border-red-500/30' : 'bg-slate-800/50 border-slate-600/30'}`}>
              <button
                onClick={(e) => { e.stopPropagation(); setMemoryExpanded(!memoryExpanded); }}
                className={`w-full text-left px-2 py-1.5 flex items-center justify-between ${action.memoryInjection.count > 0 ? 'text-purple-400' : action.memoryInjection.error ? 'text-red-400' : 'text-slate-400'}`}
              >
                <div className="text-xs uppercase flex items-center gap-2">
                  <span>Hindsight Memory</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${action.memoryInjection.count > 0 ? 'bg-purple-500/30' : action.memoryInjection.error ? 'bg-red-500/30' : 'bg-slate-600/30'}`}>
                    {action.memoryInjection.error ? 'Error' : `${action.memoryInjection.count} results`}
                  </span>
                </div>
                <span className="text-[10px]">{memoryExpanded ? '▼' : '▶'}</span>
              </button>
              {memoryExpanded && (
                <div className="px-2 pb-2">
                  {/* Debug info - bank and query */}
                  {(action.memoryInjection.bankId || action.memoryInjection.query) && (
                    <div className="text-[10px] text-slate-500 mb-2 font-mono space-y-0.5">
                      {action.memoryInjection.bankId && <div>Bank: {action.memoryInjection.bankId}</div>}
                      {action.memoryInjection.query && <div>Query: {action.memoryInjection.query.slice(0, 100)}...</div>}
                    </div>
                  )}
                  {action.memoryInjection.error ? (
                    <div className="text-red-300 text-xs font-mono">
                      {action.memoryInjection.error}
                    </div>
                  ) : action.memoryInjection.context ? (
                    <div className="text-purple-200 text-xs font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {action.memoryInjection.context}
                    </div>
                  ) : (
                    <div className="text-slate-400 text-xs italic">
                      {action.memoryInjection.count === 0 ? 'No relevant memories found' : 'Memory context not available'}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
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
    // Hard mode city grid state
    agentGridRow,
    agentGridCol,
    agentCurrentBuilding,
  } = useGameStore();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedRecipient, setSelectedRecipient] = useState<string>('');
  const [expandedAction, setExpandedAction] = useState<number | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);
  const [buildingInfo, setBuildingInfo] = useState<BuildingInfo | null>(null);
  const [showDemoSettings, setShowDemoSettings] = useState(false);
  const [showAgentModel, setShowAgentModel] = useState(false);
  const [showBuildingLayout, setShowBuildingLayout] = useState(false);
  const [selectedModel, setSelectedModel] = useState('openai/gpt-4o');
  const [difficulty, setDifficulty] = useState<Difficulty>('easy');

  // Hindsight settings
  const [hindsightInject, setHindsightInject] = useState(true);
  const [hindsightReflect, setHindsightReflect] = useState(false);
  const [hindsightStore, setHindsightStore] = useState(true);
  const [hindsightQuery, setHindsightQuery] = useState('');
  const [hindsightMission, setHindsightMission] = useState('');

  // Global hindsight URL (can be overridden per-config)
  const [globalHindsightUrl, setGlobalHindsightUrl] = useState('http://localhost:8888');
  const [hindsightUrlInput, setHindsightUrlInput] = useState('http://localhost:8888');

  // Bank management state
  const [bankHistory, setBankHistory] = useState<string[]>([]);
  const [currentBankId, setCurrentBankId] = useState<string | null>(null);
  const [bankInput, setBankInput] = useState('');

  // Mental models state
  interface MentalModel {
    id: string;
    name: string;
    content?: string;
    subtype?: string;
    created_at?: string;
  }
  const [mentalModels, setMentalModels] = useState<MentalModel[]>([]);
  const [mentalModelsLoading, setMentalModelsLoading] = useState(false);
  const [mentalModelsExpanded, setMentalModelsExpanded] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(5);
  const [deliveriesSinceRefresh, setDeliveriesSinceRefresh] = useState(0);

  // Available models
  const modelOptions = [
    { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini', description: 'Fast & cheap, good for simple tasks' },
    { id: 'openai/gpt-4o', name: 'GPT-4o', description: 'Balanced performance' },
    { id: 'openai/o1', name: 'o1', description: 'Reasoning model, slower but smarter' },
    { id: 'openai/o3-mini', name: 'o3 Mini', description: 'Latest reasoning model' },
  ];

  // Hindsight presets
  const hindsightPresets = [
    { id: 'baseline', name: 'Baseline', description: 'No memory - nothing stored or recalled', inject: false, reflect: false, store: false },
    { id: 'recall', name: 'Recall', description: 'Store all deliveries, inject relevant memories', inject: true, reflect: false, store: true },
    { id: 'reflect', name: 'Reflect', description: 'Store all, use AI-synthesized insights', inject: true, reflect: true, store: true },
  ];

  // Memory mode state (controls hindsight settings)
  // UI mode still uses simplified memory modes (maps to AgentMode for configs)
  type MemoryMode = 'baseline' | 'recall' | 'reflect';
  const [memoryMode, setMemoryMode] = useState<MemoryMode>('recall');

  // Map UI MemoryMode to AgentMode
  const memoryModeToAgentMode = (mode: MemoryMode): AgentMode => {
    if (mode === 'baseline') return 'no_memory';
    return mode;
  };

  // Update hindsight settings when memory mode changes
  const handleMemoryModeChange = (newMode: MemoryMode) => {
    setMemoryMode(newMode);
    const preset = hindsightPresets.find(p => p.id === newMode);
    if (preset) {
      setHindsightInject(preset.inject);
      setHindsightReflect(preset.reflect);
      setHindsightStore(preset.store);
    }
  };

  // View mode state (UI vs Benchmark)
  const [viewMode, setViewMode] = useState<'ui' | 'benchmark'>('benchmark');

  // Evaluation configuration type
  interface EvalResult {
    success: boolean;
    steps: number;
    optimalSteps: number;
    pathEfficiency: number;
    recipientName: string;
    deliveryNumber: number;
    tokens: {
      prompt: number;
      completion: number;
      total: number;
    };
    latencyMs: number;
    totalTimeMs: number;
    memoryInjected: boolean;
    isRepeat?: boolean;
    // New fields for eval parity
    apiCalls?: number;
    wrongTurns?: number;
    path?: string[];
    mentalModelCount?: number;
    mentalModelObservations?: number;
    buildingCoverage?: number;
    actions?: {
      step: number;
      tool: string;
      args: Record<string, unknown>;
      result: string;
      timing: number;
      memoryCount: number;
    }[];
  }

  // Agent modes - expanded from just baseline/recall/reflect
  type AgentMode = 'no_memory' | 'filesystem' | 'recall' | 'reflect' | 'hindsight_mm' | 'hindsight_mm_nowait';

  interface EvalConfig {
    id: string;
    name: string;
    model: string;
    memoryMode: AgentMode;  // Expanded to all 6 modes
    bankId: string;
    color: string;
    enabled: boolean;
    results: EvalResult[];
    // Hindsight settings
    query: string;  // Memory query template (use {recipient} placeholder)
    mission: string;  // Bank mission for mental models
    hindsightUrl?: string;  // Optional override for hindsight URL (uses global if not set)
    // New benchmark settings
    repeatRatio: number;  // 0.0-1.0, fraction of repeat visits
    pairedMode: boolean;  // Each office visited exactly 2x
    stepMultiplier: number;  // max_steps = optimal * multiplier
    minSteps: number;
    memoryQueryMode: 'inject_once' | 'per_step' | 'both';
    waitForConsolidation: boolean;
    refreshInterval: number;  // 0 = disabled
    includeBusiness: 'always' | 'never' | 'random';  // Include business name in package
    // Advanced settings
    preseedCoverage: number;  // 0.0-1.0, fraction of building knowledge to pre-seed
    mmQueryType: 'recall' | 'reflect';  // Query method for MM modes (recall = raw facts, reflect = LLM synthesis)
  }

  // Chart settings - which charts to display
  interface ChartSettings {
    enabled: boolean;  // Master toggle
    pathEfficiency: boolean;
    stepsPerDelivery: boolean;
    cumulativeSteps: boolean;
    latencyPerDelivery: boolean;
    cumulativeLatency: boolean;
    tokensPerDelivery: boolean;
    cumulativeTokens: boolean;
    comparisonSummary: boolean;
  }

  // Generate short random ID for bank names
  const shortId = () => Math.random().toString(36).slice(2, 8);

  // Predefined colors for configs
  const configColors = [
    '#ef4444', // red
    '#f97316', // orange
    '#eab308', // yellow
    '#22c55e', // green
    '#06b6d4', // cyan
    '#3b82f6', // blue
    '#8b5cf6', // violet
    '#ec4899', // pink
  ];

  // Default query, mission, and background
  const DEFAULT_QUERY = "Where does {recipient} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries.";
  const DEFAULT_MISSION = `You are a delivery agent navigating a building to deliver packages to employees.
Your goal is to learn and remember:
- Employee locations: which floor and side of the building each employee works at
- Building layout: how floors are organized, what businesses are on each floor
- Optimal delivery paths: the fastest routes to reach different employees
- Past delivery outcomes: which deliveries succeeded and which failed

Use this knowledge to efficiently deliver packages by remembering where employees are located
rather than searching the entire building each time.`;
  // Chart settings state
  const DEFAULT_CHART_SETTINGS: ChartSettings = {
    enabled: true,
    pathEfficiency: true,
    stepsPerDelivery: true,
    cumulativeSteps: false,
    latencyPerDelivery: true,
    cumulativeLatency: false,
    tokensPerDelivery: true,
    cumulativeTokens: false,
    comparisonSummary: true,
  };

  // Config counter for naming
  const configCounterRef = useRef(0);

  // Evaluation configs state
  // Default new benchmark settings
  const DEFAULT_BENCHMARK_SETTINGS = {
    repeatRatio: 0.4,
    pairedMode: false,
    stepMultiplier: 5.0,
    minSteps: 15,
    memoryQueryMode: 'inject_once' as const,
    waitForConsolidation: true,
    refreshInterval: 5,
    includeBusiness: 'random' as const,
    preseedCoverage: 0.0,  // 0 = no preseed, 1.0 = full building knowledge
    mmQueryType: 'recall' as const,  // 'recall' or 'reflect' for MM modes
  };

  const [evalConfigs, setEvalConfigs] = useState<EvalConfig[]>([]);
  const evalConfigsRef = useRef<EvalConfig[]>([]);

  // Keep ref in sync with state for use in async callbacks
  useEffect(() => {
    evalConfigsRef.current = evalConfigs;
  }, [evalConfigs]);

  // Benchmark state
  const [ffLoopCount, setFfLoopCount] = useState(10);
  const [ffRunning, setFfRunning] = useState(false);
  const [ffProgress, setFfProgress] = useState(0);
  const [ffCurrentConfig, setFfCurrentConfig] = useState<string | null>(null);
  const [saveBenchmark, setSaveBenchmark] = useState(true);  // Save benchmark results (on by default)
  const [saveAllSteps, setSaveAllSteps] = useState(false);  // Save detailed step logs for each delivery
  const [chartSettings, setChartSettings] = useState<ChartSettings>(DEFAULT_CHART_SETTINGS);
  const ffAbortRef = useRef(false);

  // UI Mode configs - tracks results per model+memoryMode combination
  const [uiConfigs, setUiConfigs] = useState<EvalConfig[]>([]);

  // Get or create UI config for current model + memoryMode
  const getOrCreateUiConfig = useCallback((model: string, mode: MemoryMode): EvalConfig => {
    const configId = `ui-${model}-${mode}`;
    const existing = uiConfigs.find(c => c.id === configId);
    if (existing) return existing;

    // Create new config
    const modelName = modelOptions.find(m => m.id === model)?.name || model;
    const modeName = mode.charAt(0).toUpperCase() + mode.slice(1);
    const colorIndex = uiConfigs.length % configColors.length;
    const agentMode = memoryModeToAgentMode(mode);
    const newConfig: EvalConfig = {
      id: configId,
      name: `${modeName} (${modelName})`,
      model,
      memoryMode: agentMode,
      bankId: `${mode}-${shortId()}`,
      color: configColors[colorIndex],
      enabled: true,
      results: [],
      query: DEFAULT_QUERY,
      mission: DEFAULT_MISSION,
      ...DEFAULT_BENCHMARK_SETTINGS,
    };
    setUiConfigs(prev => [...prev, newConfig]);
    return newConfig;
  }, [uiConfigs]);

  // Current UI config based on selected model and memory mode
  const currentUiConfig = useMemo(() => {
    const configId = `ui-${selectedModel}-${memoryMode}`;
    return uiConfigs.find(c => c.id === configId);
  }, [uiConfigs, selectedModel, memoryMode]);

  // Current bank ID for UI mode
  // Note: Computed but UI mode uses currentUiConfig.bankId directly where needed
  void (currentUiConfig && `ui-${selectedModel}-${memoryMode}`);

  // Refresh building data function
  const refreshBuildingData = useCallback(() => {
    fetch('/api/building')
      .then(res => res.json())
      .then(data => setBuildingInfo(data))
      .catch(console.error);

    fetch('/api/building/employees')
      .then(res => res.json())
      .then(data => {
        setEmployees(data.employees);
        setSelectedRecipient(''); // Clear selection when building changes
      })
      .catch(console.error);

    fetch('/api/demo-config?app=bench')
      .then(res => res.json())
      .then(data => setDemoConfig(data))
      .catch(console.error);

    // Fetch global config (hindsight URL, etc.)
    fetch('/api/config')
      .then(res => res.json())
      .then(data => {
        if (data.hindsightUrl) {
          setGlobalHindsightUrl(data.hindsightUrl);
          setHindsightUrlInput(data.hindsightUrl);
        }
      })
      .catch(console.error);
  }, []);

  // Fetch bank history and current bank
  const refreshBankHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/memory/bank/history?app=bench');
      const data = await res.json();
      setBankHistory(data.history || []);
      setCurrentBankId(data.currentBankId || null);
    } catch (err) {
      console.error('Failed to fetch bank history:', err);
    }
  }, []);

  // Switch to an existing bank
  const switchToBank = useCallback(async (bankId: string) => {
    try {
      const res = await fetch('/api/memory/bank?app=bench', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bankId }),
      });
      if (res.ok) {
        setCurrentBankId(bankId);
        refreshBankHistory();
      }
    } catch (err) {
      console.error('Failed to switch bank:', err);
    }
  }, [refreshBankHistory]);

  // Generate a new bank
  const generateNewBank = useCallback(async () => {
    try {
      const res = await fetch('/api/memory/bank/new?app=bench', { method: 'POST' });
      const data = await res.json();
      if (data.bankId) {
        setCurrentBankId(data.bankId);
        refreshBankHistory();
      }
    } catch (err) {
      console.error('Failed to generate new bank:', err);
    }
  }, [refreshBankHistory]);

  // Set an existing bank by ID
  const setExistingBank = useCallback(async () => {
    if (!bankInput.trim()) return;
    await switchToBank(bankInput.trim());
    setBankInput('');
  }, [bankInput, switchToBank]);

  // Update global hindsight URL
  const updateHindsightUrl = useCallback(async (url: string) => {
    try {
      const res = await fetch('/api/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hindsightUrl: url || '' }),  // Empty string resets to default
      });
      if (res.ok) {
        const data = await res.json();
        setGlobalHindsightUrl(data.hindsightUrl);
        setHindsightUrlInput(data.hindsightUrl);
      }
    } catch (err) {
      console.error('Failed to update hindsight URL:', err);
    }
  }, []);

  // Fetch mental models for the current bank
  const fetchMentalModels = useCallback(async () => {
    try {
      setMentalModelsLoading(true);
      const res = await fetch(`/api/memory/mental-models?app=bench&difficulty=${difficulty}`);
      const data = await res.json();
      setMentalModels(data.models || []);
    } catch (err) {
      console.error('Failed to fetch mental models:', err);
    } finally {
      setMentalModelsLoading(false);
    }
  }, [difficulty]);

  // Trigger mental models refresh
  const triggerMentalModelsRefresh = useCallback(async () => {
    try {
      setMentalModelsLoading(true);
      const res = await fetch(`/api/memory/mental-models/refresh?app=bench&difficulty=${difficulty}`, {
        method: 'POST',
      });
      if (res.ok) {
        // Wait a bit for the refresh to process, then fetch
        setTimeout(() => {
          fetchMentalModels();
          fetchRefreshIntervalStatus();
        }, 2000);
      }
    } catch (err) {
      console.error('Failed to refresh mental models:', err);
      setMentalModelsLoading(false);
    }
  }, [difficulty, fetchMentalModels]);

  // Fetch refresh interval status
  const fetchRefreshIntervalStatus = useCallback(async () => {
    try {
      const res = await fetch(`/api/memory/refresh-interval?app=bench&difficulty=${difficulty}`);
      const data = await res.json();
      setRefreshInterval(data.interval);
      setDeliveriesSinceRefresh(data.deliveriesSinceRefresh);
    } catch (err) {
      console.error('Failed to fetch refresh interval:', err);
    }
  }, [difficulty]);

  // Update refresh interval
  const updateRefreshInterval = useCallback(async (newInterval: number) => {
    try {
      const res = await fetch(`/api/memory/refresh-interval?app=bench&difficulty=${difficulty}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval: newInterval }),
      });
      if (res.ok) {
        setRefreshInterval(newInterval);
      }
    } catch (err) {
      console.error('Failed to update refresh interval:', err);
    }
  }, [difficulty]);

  // Fetch employees, demo config, difficulty, building info, and bank history on mount
  useEffect(() => {
    fetch('/api/difficulty?app=bench')
      .then(res => res.json())
      .then(data => {
        const diff = data.difficulty as Difficulty;
        setDifficulty(diff);

        // Fetch refresh interval status for the correct difficulty
        fetch(`/api/memory/refresh-interval?app=bench&difficulty=${diff}`)
          .then(res => res.json())
          .then(intervalData => {
            setRefreshInterval(intervalData.interval);
            setDeliveriesSinceRefresh(intervalData.deliveriesSinceRefresh);
          })
          .catch(console.error);
      })
      .catch(console.error);

    refreshBuildingData();
    refreshBankHistory();
  }, [refreshBuildingData, refreshBankHistory]);

  // Change difficulty handler
  const changeDifficulty = useCallback(async (newDifficulty: Difficulty) => {
    if (newDifficulty === difficulty) return;
    try {
      const res = await fetch('/api/difficulty?app=bench', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ difficulty: newDifficulty }),
      });
      if (res.ok) {
        setDifficulty(newDifficulty);
        // Dispatch event to Phaser game to update scene
        window.dispatchEvent(new CustomEvent('game-event', {
          detail: { type: 'set_difficulty', payload: { difficulty: newDifficulty } }
        }));
        // Refresh building data for new difficulty
        refreshBuildingData();
      }
    } catch (err) {
      console.error('Failed to change difficulty:', err);
    }
  }, [difficulty, refreshBuildingData]);

  // Auto-expand latest action when it changes
  useEffect(() => {
    if (actions.length > 0) {
      setExpandedAction(actions.length - 1);
    }
  }, [actions.length]);

  // Get hindsight settings with current bank ID
  const getHindsightSettingsWithBank = useCallback(() => {
    // Ensure config exists for current model + memoryMode
    const config = getOrCreateUiConfig(selectedModel, memoryMode);
    return {
      inject: hindsightInject,
      reflect: hindsightReflect,
      store: hindsightStore,
      bankId: config.bankId,
      query: hindsightQuery || undefined,  // Custom memory query (optional)
      mission: hindsightMission || undefined,  // Bank mission for mental models (optional)
    };
  }, [getOrCreateUiConfig, selectedModel, memoryMode, hindsightInject, hindsightReflect, hindsightStore, hindsightQuery, hindsightMission]);

  const handleStartDelivery = () => {
    if (selectedRecipient) {
      const settings = getHindsightSettingsWithBank();
      startDelivery(selectedRecipient, includeBusiness, maxSteps, selectedModel, settings);
    }
  };

  const handleRandomDelivery = () => {
    if (employees.length > 0) {
      const randomEmployee = employees[Math.floor(Math.random() * employees.length)];
      setSelectedRecipient(randomEmployee.name);
      const settings = getHindsightSettingsWithBank();
      startDelivery(randomEmployee.name, includeBusiness, maxSteps, selectedModel, settings);
    }
  };

  // Track UI mode delivery results
  const trackUiDeliveryResult = useCallback((success: boolean, steps: number, recipientName: string) => {
    const configId = `ui-${selectedModel}-${memoryMode}`;
    const optimalSteps = 3; // Default estimate for UI mode
    setUiConfigs(prev => prev.map(c => {
      if (c.id === configId) {
        const newResult: EvalResult = {
          success,
          steps,
          optimalSteps,
          pathEfficiency: Math.min(1.0, optimalSteps / steps),
          recipientName,
          deliveryNumber: c.results.length + 1,
          tokens: { prompt: 0, completion: 0, total: 0 },
          latencyMs: 0,
          totalTimeMs: 0,
          memoryInjected: false,
        };
        return {
          ...c,
          results: [...c.results, newResult],
        };
      }
      return c;
    }));
  }, [selectedModel, memoryMode]);

  // Track when deliveries complete - watch history length and delivery status
  const lastHistoryLength = useRef(history.length);
  useEffect(() => {
    // Only in UI mode and when history has grown
    if (viewMode === 'ui' && history.length > lastHistoryLength.current) {
      const newResults = history.slice(lastHistoryLength.current);
      for (const result of newResults) {
        trackUiDeliveryResult(result.success, result.steps, result.recipientName);
      }
    }
    lastHistoryLength.current = history.length;
  }, [history.length, viewMode, trackUiDeliveryResult]);

  const handleResetMemory = () => {
    if (confirm('This will clear all agent memories and delivery history. Continue?')) {
      resetMemory();
      resetHistory();
      clearAllResults();
      setUiConfigs([]); // Clear UI mode tracking configs
      lastHistoryLength.current = 0;
      // Refresh bank history after WebSocket sends reset event
      setTimeout(() => refreshBankHistory(), 500);
    }
  };

  // Helper to get hindsight settings for an agent mode
  const getHindsightForMode = (mode: AgentMode) => {
    // Map agent modes to hindsight settings
    switch (mode) {
      case 'no_memory':
        return { inject: false, reflect: false, store: false };
      case 'filesystem':
        return { inject: false, reflect: false, store: false };
      case 'recall':
        return { inject: true, reflect: false, store: true };
      case 'reflect':
        return { inject: true, reflect: true, store: true };
      case 'hindsight_mm':
      case 'hindsight_mm_nowait':
        return { inject: true, reflect: true, store: true };
      default:
        return { inject: false, reflect: false, store: false };
    }
  };

  // Benchmark handlers - runs all enabled configs IN PARALLEL
  const runFastForward = useCallback(async (count: number) => {
    setFfRunning(true);
    setFfProgress(0);
    ffAbortRef.current = false;

    const enabledConfigs = evalConfigs.filter(c => c.enabled);
    const totalDeliveries = count * enabledConfigs.length;
    let completed = 0;

    // Clear previous results for enabled configs
    setEvalConfigs(prev => prev.map(c => c.enabled ? { ...c, results: [] } : c));

    // Run a single delivery for a config
    const runSingleDelivery = async (config: EvalConfig, deliveryNum: number) => {
      if (ffAbortRef.current) return;

      const hs = getHindsightForMode(config.memoryMode);

      try {
        // Backend calculates max_steps from optimal path: max(minSteps, optimal * stepMultiplier)
        // maxSteps from UI is passed as hard cap (if set)
        const res = await fetch('/api/delivery/fast', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            includeBusiness: config.includeBusiness,
            maxSteps: maxSteps || null,  // Hard cap from global UI setting (null = no cap)
            stepMultiplier: config.stepMultiplier,
            minSteps: config.minSteps,
            model: config.model,
            // Per-config benchmark settings
            repeatRatio: config.repeatRatio,
            pairedMode: config.pairedMode,
            memoryQueryMode: config.memoryQueryMode,
            waitForConsolidation: config.waitForConsolidation,
            refreshInterval: config.refreshInterval,
            preseedCoverage: config.preseedCoverage || 0,
            mmQueryType: config.mmQueryType || 'recall',
            hindsight: {
              inject: hs.inject,
              reflect: hs.reflect,
              store: hs.store,
              bankId: config.bankId,
              query: config.query || undefined,
              mission: config.mission || undefined,  // Always pass mission for bank setup
              url: config.hindsightUrl || globalHindsightUrl,  // Per-config override or global
            },
          }),
        });
        const result = await res.json();

        // Update this config's results
        setEvalConfigs(prev => prev.map(c => {
          if (c.id === config.id) {
            const newResult: EvalResult = {
              success: result.success,
              steps: result.steps,
              optimalSteps: result.optimalSteps || 3,
              pathEfficiency: result.pathEfficiency || 0,
              recipientName: result.recipientName || 'Unknown',
              deliveryNumber: deliveryNum,
              tokens: result.tokens || { prompt: 0, completion: 0, total: 0 },
              latencyMs: result.latencyMs || 0,
              totalTimeMs: result.totalTimeMs || 0,
              memoryInjected: result.memoryInjected || false,
              // New fields for eval parity
              apiCalls: result.apiCalls,
              wrongTurns: result.wrongTurns,
              path: result.path,
              mentalModelCount: result.mentalModelCount,
              mentalModelObservations: result.mentalModelObservations,
              buildingCoverage: result.buildingCoverage,
            };
            // Include full action logs if saveAllSteps is enabled
            if (saveAllSteps && result.actions) {
              newResult.actions = result.actions;
            }
            return {
              ...c,
              results: [...c.results, newResult],
            };
          }
          return c;
        }));
      } catch (err) {
        console.error('Benchmark error:', err);
      }

      completed++;
      setFfProgress((completed / totalDeliveries) * 100);
    };

    // Run all configs in parallel - each config runs its deliveries sequentially
    // (sequential per config so memories build up, but configs run in parallel)
    const configPromises = enabledConfigs.map(async (config) => {
      for (let i = 0; i < count; i++) {
        if (ffAbortRef.current) break;
        setFfCurrentConfig(config.id);
        await runSingleDelivery(config, i + 1);
      }
    });

    await Promise.all(configPromises);

    setFfCurrentConfig(null);
    setFfRunning(false);

    // Update refresh interval status after all deliveries complete
    fetchRefreshIntervalStatus();

    // Auto-save if saveBenchmark is enabled
    if (saveBenchmark && !ffAbortRef.current) {
      try {
        // Get updated configs with results (use ref to get latest state)
        const configsWithResults = evalConfigsRef.current.filter(c => c.enabled && c.results.length > 0);

        // Format results for the save endpoint
        const resultsToSave = configsWithResults.map(config => {
          const results = config.results;
          const successCount = results.filter(r => r.success).length;
          const totalSteps = results.reduce((s, r) => s + r.steps, 0);
          const totalOptimalSteps = results.reduce((s, r) => s + r.optimalSteps, 0);

          // Use real efficiency from results
          const efficiencyByEpisode = results.map(r => r.pathEfficiency);
          const tokensByEpisode = results.map(r => r.tokens.total);
          const latencyByEpisode = results.map(r => r.latencyMs);

          // Token totals
          const totalPromptTokens = results.reduce((s, r) => s + r.tokens.prompt, 0);
          const totalCompletionTokens = results.reduce((s, r) => s + r.tokens.completion, 0);
          const totalTokens = totalPromptTokens + totalCompletionTokens;
          const totalLatencyMs = results.reduce((s, r) => s + r.latencyMs, 0);

          // Learning metrics
          const mid = Math.floor(results.length / 2);
          const firstHalfEff = mid > 0 ? efficiencyByEpisode.slice(0, mid).reduce((a, b) => a + b, 0) / mid : 0;
          const secondHalfEff = results.length - mid > 0 ? efficiencyByEpisode.slice(mid).reduce((a, b) => a + b, 0) / (results.length - mid) : 0;

          // Find convergence (first episode with >= 90% efficiency)
          let convergence = 0;
          for (let i = 0; i < efficiencyByEpisode.length; i++) {
            if (efficiencyByEpisode[i] >= 0.9) {
              convergence = i + 1;
              break;
            }
          }

          return {
            config: {
              name: config.name,
              mode: config.memoryMode,
              model: config.model,
              numDeliveries: results.length,
              repeatRatio: config.repeatRatio,
              pairedMode: config.pairedMode,
              difficulty: difficulty,
              refreshInterval: config.refreshInterval,
            },
            summary: {
              totalDeliveries: results.length,
              successfulDeliveries: successCount,
              failedDeliveries: results.length - successCount,
              successRate: results.length > 0 ? successCount / results.length : 0,
              totalSteps,
              totalOptimalSteps,
              avgPathEfficiency: efficiencyByEpisode.length > 0 ? efficiencyByEpisode.reduce((a, b) => a + b, 0) / efficiencyByEpisode.length : 0,
              totalTokens: { prompt: totalPromptTokens, completion: totalCompletionTokens, total: totalTokens },
              totalLatencyMs,
              avgLatencyMs: results.length > 0 ? totalLatencyMs / results.length : 0,
            },
            learning: {
              convergenceEpisode: convergence,
              firstHalfEfficiency: firstHalfEff,
              secondHalfEfficiency: secondHalfEff,
              improvement: secondHalfEff - firstHalfEff,
            },
            timeSeries: {
              efficiencyByEpisode,
              tokensByEpisode,
              latencyByEpisode,
            },
            deliveries: results.map((r, i) => {
              const delivery: Record<string, unknown> = {
                deliveryId: i + 1,
                recipient: r.recipientName,
                business: null,
                success: r.success,
                stepsTaken: r.steps,
                optimalSteps: r.optimalSteps,
                pathEfficiency: r.pathEfficiency,
                tokens: r.tokens,
                latencyMs: r.latencyMs,
                memoryInjected: r.memoryInjected,
                memoryQueryCount: r.memoryInjected ? 1 : 0,
                consolidationTriggered: false,
                isRepeat: r.isRepeat || false,
                // New fields for eval parity
                apiCalls: r.apiCalls || 0,
                wrongTurns: r.wrongTurns || 0,
                path: r.path || [],
                mentalModelCount: r.mentalModelCount || 0,
                mentalModelObservations: r.mentalModelObservations || 0,
                buildingCoverage: r.buildingCoverage || 0,
              };
              // Include actions if saveAllSteps is enabled
              if (saveAllSteps && r.actions) {
                delivery.actions = r.actions;
              }
              return delivery;
            }),
          };
        });

        if (resultsToSave.length > 0) {
          const saveRes = await fetch('/api/benchmark/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              results: resultsToSave,
              generateCharts: chartSettings.enabled,
              saveDetailedLogs: saveAllSteps,
            }),
          });
          const saveResult = await saveRes.json();
          console.log('Benchmark saved:', saveResult);
        }
      } catch (err) {
        console.error('Failed to save benchmark:', err);
      }
    }
  }, [includeBusiness, maxSteps, saveAllSteps, saveBenchmark, chartSettings.enabled, difficulty, fetchRefreshIntervalStatus]);

  // Remove a config
  const removeEvalConfig = useCallback((id: string) => {
    setEvalConfigs(prev => prev.filter(c => c.id !== id));
  }, []);

  // Update a config
  const updateEvalConfig = useCallback((id: string, updates: Partial<EvalConfig>) => {
    setEvalConfigs(prev => prev.map(c => c.id === id ? { ...c, ...updates } : c));
  }, []);

  // Clear all results
  const clearAllResults = useCallback(() => {
    setEvalConfigs(prev => prev.map(c => ({ ...c, results: [], bankId: `bank-${c.id}-${Date.now()}` })));
  }, []);

  const stopFastForward = useCallback(() => {
    ffAbortRef.current = true;
  }, []);

  // Export evaluation results to JSON file
  const exportResults = useCallback(() => {
    const exportData = {
      exportedAt: new Date().toISOString(),
      settings: {
        deliveriesPerConfig: ffLoopCount,
        maxSteps: maxSteps || 150,
        includeBusiness,
      },
      configs: evalConfigs.filter(c => c.results.length > 0).map(config => ({
        name: config.name,
        model: config.model,
        memoryMode: config.memoryMode,
        bankId: config.bankId,
        results: config.results,
        summary: {
          totalRuns: config.results.length,
          successes: config.results.filter(r => r.success).length,
          successRate: config.results.length > 0
            ? config.results.filter(r => r.success).length / config.results.length
            : 0,
          avgSteps: config.results.length > 0
            ? config.results.reduce((sum, r) => sum + r.steps, 0) / config.results.length
            : 0,
          minSteps: config.results.length > 0 ? Math.min(...config.results.map(r => r.steps)) : 0,
          maxSteps: config.results.length > 0 ? Math.max(...config.results.map(r => r.steps)) : 0,
        },
      })),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `delivery-eval-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [evalConfigs, ffLoopCount, maxSteps, includeBusiness]);

  // Chart data - steps per delivery
  const chartData = history.map((h, i) => ({
    delivery: i + 1,
    steps: h.steps,
    success: h.success,
    optimal: getOptimalSteps(h.recipientName, employees),
  }));

  function getOptimalSteps(name: string, emps: Employee[]): number {
    const emp = emps.find(e => e.name === name);
    if (!emp) return 5;
    // Optimal: check location (1) + move floors + move sides + deliver (1)
    // From floor 1 middle: abs(emp.floor - 1) + (emp.side !== 'middle' ? 1 : 0) + 2
    return Math.abs(emp.floor - 1) + (emp.side !== 'middle' ? 1 : 0) + 2;
  }

  const avgSteps = history.length > 0
    ? (history.reduce((sum, h) => sum + h.steps, 0) / history.length).toFixed(1)
    : '-';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100">
      {/* Header */}
      <header className="bg-slate-900/50 border-b border-slate-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div>
              <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-blue-400 font-mono">
                Delivery Agent Benchmark Demo
              </h1>
              <p className="text-slate-500 text-sm">
                AI agent learning with Hindsight memory
              </p>
            </div>
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
            {/* Bank Management - UI mode only */}
            {viewMode === 'ui' && (
              <div className="relative group flex items-center gap-1">
                <button className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 px-3 py-1.5 rounded-lg transition-colors">
                  <span className="text-xs text-slate-400">Bank:</span>
                  <code className="text-xs text-purple-400 font-mono">{currentBankId || 'None'}</code>
                  <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {currentBankId && (
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(currentBankId);
                    }}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg transition-colors"
                    title="Copy bank ID to clipboard"
                  >
                    <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                )}
                {/* Dropdown */}
                <div className="absolute right-0 top-full mt-1 w-64 bg-slate-800 border border-slate-600 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  <div className="p-3 space-y-3">
                    {/* Generate New Bank */}
                    <button
                      onClick={generateNewBank}
                      disabled={deliveryStatus === 'running'}
                      className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-purple-600/20 hover:bg-purple-600/30 disabled:bg-slate-700 disabled:cursor-not-allowed border border-purple-500/30 rounded text-sm text-purple-300 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      New Bank
                    </button>

                    {/* Bank History */}
                    {bankHistory.length > 0 && (
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Recent Banks</label>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {bankHistory.map((bankId) => (
                            <button
                              key={bankId}
                              onClick={() => switchToBank(bankId)}
                              className={`w-full text-left px-2 py-1.5 text-xs font-mono rounded transition-colors flex items-center justify-between ${
                                bankId === currentBankId
                                  ? 'bg-purple-600/30 text-purple-300 cursor-default'
                                  : 'text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                              }`}
                              disabled={bankId === currentBankId}
                            >
                              <span className="truncate">{bankId}</span>
                              {bankId === currentBankId && (
                                <span className="text-[10px] text-purple-400 ml-2">current</span>
                              )}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Use Existing Bank */}
                    <div className="border-t border-slate-700 pt-2">
                      <label className="block text-xs text-slate-500 mb-1">Use Existing Bank</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={bankInput}
                          onChange={(e) => setBankInput(e.target.value)}
                          placeholder="bench-xxxxxxxx"
                          className="flex-1 bg-slate-700/50 border border-slate-600 rounded px-2 py-1 text-xs text-white focus:border-purple-500 focus:outline-none"
                          onKeyDown={(e) => e.key === 'Enter' && setExistingBank()}
                        />
                        <button
                          onClick={setExistingBank}
                          disabled={!bankInput.trim()}
                          className="px-2 py-1 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white text-xs rounded transition-colors"
                        >
                          Set
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 max-w-7xl mx-auto">
        {/* View Mode Tabs */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex gap-2 p-1 bg-slate-800/50 rounded-lg inline-flex">
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
                onClick={() => setViewMode('benchmark')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  viewMode === 'benchmark'
                    ? 'bg-gradient-to-r from-yellow-600 to-orange-500 text-white shadow-lg'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                Benchmark
              </button>
            </div>

            {/* Difficulty selector - UI mode only */}
            {viewMode === 'ui' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 bg-slate-800/50 rounded-lg p-1">
                  {(['easy', 'medium', 'hard'] as Difficulty[]).map((d) => (
                    <button
                      key={d}
                      onClick={() => changeDifficulty(d)}
                      disabled={deliveryStatus === 'running'}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                        difficulty === d
                          ? d === 'easy' ? 'bg-green-600 text-white'
                            : d === 'medium' ? 'bg-yellow-600 text-white'
                            : 'bg-red-600 text-white'
                          : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {d.charAt(0).toUpperCase() + d.slice(1)}
                    </button>
                  ))}
                </div>
                <span className="text-xs text-slate-500">
                  {difficulty === 'easy' ? '3 floors' : difficulty === 'medium' ? '3 buildings' : '12 buildings'}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Demo Settings Collapsible - UI mode only */}
        {viewMode === 'ui' && (
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

          {showDemoSettings && (
            <div className="mt-3 bg-slate-800/50 rounded-xl p-4 border border-slate-700 space-y-4">
              {/* Model Selection - UI mode only, collapsible */}
              {viewMode === 'ui' && (
                <div>
                  <button
                    onClick={() => setShowAgentModel(!showAgentModel)}
                    className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-wider mb-2 hover:text-slate-400 transition-colors"
                  >
                    <span className={`transition-transform ${showAgentModel ? 'rotate-90' : ''}`}>
                      ▶
                    </span>
                    <span>Agent Model</span>
                    <span className="text-slate-600 normal-case">({modelOptions.find(m => m.id === selectedModel)?.name || selectedModel})</span>
                  </button>
                  {showAgentModel && (
                    <>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {modelOptions.map(model => (
                          <button
                            key={model.id}
                            onClick={() => setSelectedModel(model.id)}
                            className={`text-left p-3 rounded-lg border transition-all ${
                              selectedModel === model.id
                                ? 'bg-blue-500/20 border-blue-500/50 ring-1 ring-blue-500/30'
                                : 'bg-slate-900/50 border-slate-700 hover:border-slate-600'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${
                                selectedModel === model.id ? 'bg-blue-400' : 'bg-slate-600'
                              }`} />
                              <span className={`font-medium ${
                                selectedModel === model.id ? 'text-blue-300' : 'text-slate-300'
                              }`}>
                                {model.name}
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-1 ml-5">{model.description}</p>
                          </button>
                        ))}
                      </div>
                      {/* Custom Model Input */}
                      <div className="mt-3">
                        <label className="text-xs text-slate-400 block mb-1">Custom Model (overrides selection above)</label>
                        <input
                          type="text"
                          value={selectedModel}
                          onChange={(e) => setSelectedModel(e.target.value)}
                          placeholder="e.g., anthropic/claude-3-5-sonnet"
                          className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-slate-500 focus:outline-none focus:border-blue-500"
                        />
                      </div>
                    </>
                  )}
                </div>
              )}

              {demoConfig && (
                <>
                  {/* System Prompt */}
                  <div>
                    <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">System Prompt</h3>
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                      <code className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                        {demoConfig.systemPrompt}
                      </code>
                      {memoryMode !== 'baseline' && (
                        <div className="mt-2 pt-2 border-t border-slate-700">
                          <code className={`text-sm font-mono whitespace-pre-wrap ${memoryMode === 'recall' ? 'text-purple-400' : 'text-cyan-400'}`}>
                            {'\n'}# Relevant Memory{'\n'}{'<memory from hindsight query>'}
                          </code>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* User Prompt */}
                  <div>
                    <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">User Prompt</h3>
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                      <code className="text-blue-400 text-sm font-mono whitespace-pre-wrap">
                        Please deliver this package: Package #{"<id>"}: To {"<recipient_name>"} {includeBusiness ? '[at <business_name>]' : ''}
                      </code>
                    </div>
                  </div>
                </>
              )}

              {/* Hindsight Memory Settings - UI mode only */}
              {viewMode === 'ui' && (
                <div>
                  <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-3">Hindsight Memory</h3>

                  {/* Memory Mode Buttons */}
                  <div className="flex gap-2 mb-3">
                    <button
                      onClick={() => handleMemoryModeChange('baseline')}
                      className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        memoryMode === 'baseline'
                          ? 'bg-slate-500/30 border border-slate-400/50 text-slate-300'
                          : 'bg-slate-900/50 border border-slate-700 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      Baseline
                    </button>
                    <button
                      onClick={() => handleMemoryModeChange('recall')}
                      className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        memoryMode === 'recall'
                          ? 'bg-purple-500/30 border border-purple-500/50 text-purple-300'
                          : 'bg-slate-900/50 border border-slate-700 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      Recall
                    </button>
                    <button
                      onClick={() => handleMemoryModeChange('reflect')}
                      className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        memoryMode === 'reflect'
                          ? 'bg-cyan-500/30 border border-cyan-500/50 text-cyan-300'
                          : 'bg-slate-900/50 border border-slate-700 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      Reflect
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 mb-3">
                    {hindsightPresets.find(p => p.id === memoryMode)?.description}
                  </p>

                  {/* Individual Toggle Controls */}
                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-slate-300">Inject Memories</span>
                        <p className="text-xs text-slate-500">Add relevant memories to LLM context</p>
                      </div>
                      <button
                        onClick={() => setHindsightInject(!hindsightInject)}
                        className={`w-12 h-6 rounded-full transition-all ${
                          hindsightInject ? 'bg-green-500' : 'bg-slate-600'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${
                          hindsightInject ? 'translate-x-6' : 'translate-x-0.5'
                        }`} />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-slate-300">Use Reflect</span>
                        <p className="text-xs text-slate-500">Use AI-synthesized insights instead of raw facts</p>
                      </div>
                      <button
                        onClick={() => setHindsightReflect(!hindsightReflect)}
                        className={`w-12 h-6 rounded-full transition-all ${
                          hindsightReflect ? 'bg-cyan-500' : 'bg-slate-600'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${
                          hindsightReflect ? 'translate-x-6' : 'translate-x-0.5'
                        }`} />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-slate-300">Store Deliveries</span>
                        <p className="text-xs text-slate-500">Save delivery outcomes to memory bank</p>
                      </div>
                      <button
                        onClick={() => setHindsightStore(!hindsightStore)}
                        className={`w-12 h-6 rounded-full transition-all ${
                          hindsightStore ? 'bg-purple-500' : 'bg-slate-600'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${
                          hindsightStore ? 'translate-x-6' : 'translate-x-0.5'
                        }`} />
                      </button>
                    </div>
                    {demoConfig && (
                      <div className="flex items-center justify-between pt-2 border-t border-slate-700">
                        <span className="text-sm text-slate-400">API URL</span>
                        <code className="text-purple-400 font-mono text-xs">{demoConfig.hindsight.apiUrl}</code>
                      </div>
                    )}
                  </div>

                  {/* Memory Query Input */}
                  <div className="mt-3">
                    <label className="text-xs text-slate-400 block mb-1">
                      Memory Query (optional)
                    </label>
                    <input
                      type="text"
                      value={hindsightQuery}
                      onChange={(e) => setHindsightQuery(e.target.value)}
                      placeholder="Where does {recipient} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries."
                      className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-slate-500 focus:outline-none focus:border-purple-500"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Use {'{recipient}'} as a placeholder. Default query asks about recipient location.
                    </p>
                  </div>

                  {/* Bank Mission Input */}
                  <div className="mt-3">
                    <label className="text-xs text-slate-400 block mb-1">
                      Bank Mission (optional)
                    </label>
                    <textarea
                      value={hindsightMission}
                      onChange={(e) => setHindsightMission(e.target.value)}
                      placeholder={DEFAULT_MISSION}
                      rows={4}
                      className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Comprehensive description for mental models - what the agent should learn and remember.
                    </p>
                  </div>

                  {/* Mental Models Section */}
                  <div className="mt-4 border-t border-slate-700 pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h4 className="text-sm text-slate-300 font-medium">Mental Models</h4>
                        <p className="text-xs text-slate-500">Higher-level patterns learned from delivery experiences</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={fetchMentalModels}
                          disabled={mentalModelsLoading}
                          className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded text-slate-300 disabled:opacity-50"
                        >
                          {mentalModelsLoading ? '...' : 'Fetch'}
                        </button>
                        <button
                          onClick={triggerMentalModelsRefresh}
                          disabled={mentalModelsLoading}
                          className="px-2 py-1 text-xs bg-purple-600 hover:bg-purple-500 rounded text-white disabled:opacity-50"
                        >
                          {mentalModelsLoading ? 'Refreshing...' : 'Refresh'}
                        </button>
                        {/* Auto-refresh controls */}
                        <div className="flex items-center gap-1 ml-2 border-l border-slate-600 pl-2">
                          <span className="text-slate-500 text-xs">Auto:</span>
                          <select
                            value={refreshInterval}
                            onChange={(e) => updateRefreshInterval(parseInt(e.target.value))}
                            className="px-1 py-0.5 bg-slate-700 border border-slate-600 rounded text-slate-300 text-xs"
                          >
                            <option value={0}>Off</option>
                            <option value={1}>1</option>
                            <option value={3}>3</option>
                            <option value={5}>5</option>
                            <option value={10}>10</option>
                          </select>
                          {refreshInterval > 0 && (
                            <span className="text-slate-500 text-xs">
                              ({deliveriesSinceRefresh}/{refreshInterval})
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {mentalModels.length > 0 ? (
                      <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden">
                        <button
                          onClick={() => setMentalModelsExpanded(!mentalModelsExpanded)}
                          className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-800/50"
                        >
                          <span className="text-sm text-slate-300">
                            {mentalModels.length} mental model{mentalModels.length !== 1 ? 's' : ''} found
                          </span>
                          <span className="text-slate-400 text-xs">{mentalModelsExpanded ? '▼' : '▶'}</span>
                        </button>
                        {mentalModelsExpanded && (
                          <div className="border-t border-slate-700 max-h-48 overflow-y-auto">
                            {mentalModels.map((model, idx) => (
                              <div key={model.id || idx} className="px-3 py-2 border-b border-slate-700/50 last:border-b-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-xs text-purple-400 font-mono">{model.subtype || 'model'}</span>
                                  {model.name && <span className="text-xs text-slate-400">{model.name}</span>}
                                </div>
                                {model.content && (
                                  <p className="text-xs text-slate-300 whitespace-pre-wrap">{model.content}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="bg-slate-900/50 rounded-lg border border-slate-700 px-3 py-4 text-center">
                        <p className="text-xs text-slate-500">
                          No mental models yet. Run some deliveries to build up memories, then click Refresh.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {demoConfig && (
                <>
                  {/* Available Tools */}
                  <div>
                    <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Available Tools</h3>
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
                      <span>Building Layout</span>
                    </button>

                    {showBuildingLayout && buildingInfo && (
                      <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-4">
                        <div className="text-sm text-slate-400 mb-2">
                          {buildingInfo.floors} floors • {buildingInfo.businesses.length} businesses • {buildingInfo.businesses.reduce((acc, b) => acc + b.employees.length, 0)} employees
                        </div>

                        {/* Render floors from top to bottom */}
                        {[...Array(buildingInfo.floors)].map((_, i) => {
                          const floorNum = buildingInfo.floors - i;
                          const floorBusinesses = buildingInfo.businesses.filter(b => b.floor === floorNum);
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
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
        )}

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
                gridRow={agentGridRow}
                gridCol={agentGridCol}
                currentBuilding={agentCurrentBuilding}
              />

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
                {/* Legend for UI configs */}
                {uiConfigs.filter(c => c.results.length > 0).length > 0 ? (
                  <div className="flex flex-wrap gap-3">
                    {uiConfigs.filter(c => c.results.length > 0).map(config => (
                      <div key={config.id} className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: config.color }} />
                        <span className="text-xs text-slate-400">{config.name}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-slate-500">
                    Avg: <span className="text-white font-mono">{avgSteps}</span> steps/delivery
                  </span>
                )}
              </div>
              {uiConfigs.filter(c => c.results.length >= 2).length === 0 && history.length < 2 ? (
                <div className="h-32 flex items-center justify-center text-slate-500 text-sm">
                  Complete at least 2 deliveries to see learning progress
                </div>
              ) : uiConfigs.some(c => c.results.length >= 2) ? (
                /* Multi-series chart when tracking configs */
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart>
                    <XAxis
                      dataKey="delivery"
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                      type="number"
                      domain={[1, 'auto']}
                      allowDecimals={false}
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
                    <ReferenceLine y={3} stroke="#4ade80" strokeDasharray="3 3" />
                    {uiConfigs.filter(c => c.results.length > 0).map(config => (
                      <Line
                        key={config.id}
                        data={config.results.map((r, i) => ({ delivery: i + 1, steps: r.steps, name: config.name }))}
                        type="monotone"
                        dataKey="steps"
                        name={config.name}
                        stroke={config.color}
                        strokeWidth={2}
                        dot={{ r: 3, fill: config.color }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                /* Fallback to single-series chart */
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
                      formatter={(value, name, props) => [
                        value ?? 0,
                        name === 'steps' ? (props.payload.success ? 'Steps (Success)' : 'Steps (Failed)') : 'Optimal'
                      ]}
                    />
                    <ReferenceLine y={3} stroke="#4ade80" strokeDasharray="3 3" label={{ value: 'Optimal', fill: '#4ade80', fontSize: 10 }} />
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
                  disabled={!connected || !selectedRecipient || deliveryStatus === 'running'}
                  className="flex-1 bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-green-500/20 disabled:shadow-none"
                >
                  {deliveryStatus === 'running' ? 'Running...' : 'Start Delivery'}
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
                disabled={!connected || deliveryStatus === 'running' || employees.length === 0}
                className="w-full mt-2 bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-500 hover:to-blue-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-purple-500/20 disabled:shadow-none"
              >
                Random Delivery
              </button>

              {/* Reset Memory */}
              <button
                onClick={handleResetMemory}
                disabled={deliveryStatus === 'running'}
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
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold text-purple-300">Hindsight Memory</h2>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    memoryReflect.method === 'reflect'
                      ? 'bg-purple-600/30 text-purple-300'
                      : 'bg-blue-600/30 text-blue-300'
                  }`}>
                    {memoryReflect.method}
                  </span>
                </div>
                <div className="space-y-3">
                  {/* Query */}
                  <div>
                    <div className="text-purple-400 text-xs uppercase mb-1">Query</div>
                    <div className="text-purple-200 text-sm font-mono bg-purple-950/50 rounded p-2">
                      {memoryReflect.query}
                    </div>
                  </div>
                  {/* Memory Content */}
                  <div>
                    <div className="text-purple-400 text-xs uppercase mb-1">
                      {memoryReflect.method === 'reflect' ? 'Synthesized Memory' : `Raw Facts (${memoryReflect.count})`}
                    </div>
                    {memoryReflect.context ? (
                      <div className="text-purple-100 text-sm whitespace-pre-wrap bg-purple-950/50 rounded p-2 max-h-40 overflow-y-auto">
                        {memoryReflect.context}
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
                  {/* Raw memories for recall mode */}
                  {memoryReflect.method === 'recall' && memoryReflect.memories && memoryReflect.memories.length > 0 && (
                    <div>
                      <div className="text-purple-400 text-xs uppercase mb-1">Individual Facts</div>
                      <div className="space-y-1 max-h-32 overflow-y-auto">
                        {memoryReflect.memories.map((fact, i) => (
                          <div key={i} className="text-xs bg-purple-950/30 rounded px-2 py-1 flex items-start gap-2">
                            <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                              fact.type === 'world' ? 'bg-blue-600/30 text-blue-300' :
                              fact.type === 'experience' ? 'bg-green-600/30 text-green-300' :
                              'bg-yellow-600/30 text-yellow-300'
                            }`}>
                              {fact.type}
                            </span>
                            <span className="text-purple-200">{fact.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Timing */}
                  {memoryReflect.timing !== undefined && (
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

        {/* Benchmark Mode */}
        {viewMode === 'benchmark' && (
          <div className="space-y-6">
            {/* Top Section: Run Settings */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-4">
                  <h2 className="text-lg font-semibold text-slate-300">Run Settings</h2>
                  {/* Difficulty selector */}
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 bg-slate-700/50 rounded-lg p-1">
                      {(['easy', 'medium', 'hard'] as Difficulty[]).map((d) => (
                        <button
                          key={d}
                          onClick={() => changeDifficulty(d)}
                          disabled={ffRunning}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                            difficulty === d
                              ? d === 'easy' ? 'bg-green-600 text-white'
                                : d === 'medium' ? 'bg-yellow-600 text-white'
                                : 'bg-red-600 text-white'
                              : 'text-slate-400 hover:text-slate-300 hover:bg-slate-600'
                          }`}
                        >
                          {d.charAt(0).toUpperCase() + d.slice(1)}
                        </button>
                      ))}
                    </div>
                    <span className="text-xs text-slate-500">
                      {difficulty === 'easy' ? '3 floors' : difficulty === 'medium' ? '3 buildings' : '12 buildings'}
                    </span>
                  </div>
                </div>
                {ffRunning && (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />
                    <span className="text-sm text-yellow-400">Running...</span>
                  </div>
                )}
              </div>

              {/* Hindsight URL Setting */}
              <div className="mb-4">
                <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                  Hindsight API URL
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={hindsightUrlInput}
                    onChange={(e) => setHindsightUrlInput(e.target.value)}
                    placeholder="http://localhost:8888"
                    className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-yellow-500 focus:outline-none font-mono"
                    disabled={ffRunning}
                  />
                  <button
                    onClick={() => updateHindsightUrl(hindsightUrlInput)}
                    disabled={ffRunning || hindsightUrlInput === globalHindsightUrl}
                    className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-slate-300 rounded-lg text-sm transition-colors"
                  >
                    Set
                  </button>
                  <button
                    onClick={() => updateHindsightUrl('')}
                    disabled={ffRunning}
                    className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-slate-400 rounded-lg text-sm transition-colors"
                    title="Reset to default"
                  >
                    Reset
                  </button>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Current: <span className="font-mono text-slate-400">{globalHindsightUrl}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Deliveries per Config
                  </label>
                  <input
                    type="number"
                    value={ffLoopCount}
                    onChange={(e) => setFfLoopCount(parseInt(e.target.value) || 1)}
                    min={1}
                    max={100}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-yellow-500 focus:outline-none"
                    disabled={ffRunning}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Max Steps
                  </label>
                  <input
                    type="number"
                    value={maxSteps ?? 150}
                    onChange={(e) => setMaxSteps(parseInt(e.target.value) || 150)}
                    min={1}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-yellow-500 focus:outline-none"
                    disabled={ffRunning}
                  />
                </div>
                <div className="flex flex-col justify-end">
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={includeBusiness}
                      onChange={(e) => setIncludeBusiness(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-yellow-500 focus:ring-yellow-500 focus:ring-offset-0"
                      disabled={ffRunning}
                    />
                    <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                      Include business name
                    </span>
                  </label>
                </div>
                <div className="flex flex-col justify-end">
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={saveBenchmark}
                      onChange={(e) => setSaveBenchmark(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-green-500 focus:ring-green-500 focus:ring-offset-0"
                      disabled={ffRunning}
                    />
                    <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                      Save benchmark
                    </span>
                  </label>
                </div>
                <div className="flex flex-col justify-end">
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={saveAllSteps}
                      onChange={(e) => setSaveAllSteps(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                      disabled={ffRunning}
                    />
                    <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                      Save detailed logs
                    </span>
                  </label>
                </div>
              </div>

              {/* Chart Settings */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={chartSettings.enabled}
                      onChange={(e) => setChartSettings({ ...chartSettings, enabled: e.target.checked })}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500 focus:ring-offset-0"
                      disabled={ffRunning}
                    />
                    <span className="text-sm text-slate-300 font-medium">Show Charts</span>
                  </label>
                </div>
                {chartSettings.enabled && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
                    {[
                      { key: 'pathEfficiency', label: 'Path Efficiency' },
                      { key: 'stepsPerDelivery', label: 'Steps/Delivery' },
                      { key: 'cumulativeSteps', label: 'Cumulative Steps' },
                      { key: 'latencyPerDelivery', label: 'Latency/Delivery' },
                      { key: 'cumulativeLatency', label: 'Cumulative Latency' },
                      { key: 'tokensPerDelivery', label: 'Tokens/Delivery' },
                      { key: 'cumulativeTokens', label: 'Cumulative Tokens' },
                      { key: 'comparisonSummary', label: 'Comparison Summary' },
                    ].map(({ key, label }) => (
                      <label key={key} className="flex items-center gap-1.5 cursor-pointer text-xs">
                        <input
                          type="checkbox"
                          checked={chartSettings[key as keyof ChartSettings] as boolean}
                          onChange={(e) => setChartSettings({ ...chartSettings, [key]: e.target.checked })}
                          className="w-3 h-3 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500 focus:ring-offset-0"
                          disabled={ffRunning}
                        />
                        <span className="text-slate-400">{label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => runFastForward(ffLoopCount)}
                  disabled={ffRunning || evalConfigs.filter(c => c.enabled).length === 0}
                  className="flex-1 bg-gradient-to-r from-yellow-600 to-orange-500 hover:from-yellow-500 hover:to-orange-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-yellow-500/20 disabled:shadow-none"
                >
                  {ffRunning ? `Running...` : `Run ${ffLoopCount} deliveries × ${evalConfigs.filter(c => c.enabled).length} configs`}
                </button>
                <button
                  onClick={stopFastForward}
                  disabled={!ffRunning}
                  className="bg-red-600/80 hover:bg-red-600 disabled:bg-slate-600/50 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-colors"
                >
                  Stop
                </button>
                <button
                  onClick={clearAllResults}
                  disabled={ffRunning || !evalConfigs.some(c => c.results.length > 0)}
                  className="bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-400 hover:text-slate-300 disabled:bg-slate-800 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-colors"
                >
                  Clear
                </button>
                <button
                  onClick={exportResults}
                  disabled={!evalConfigs.some(c => c.results.length > 0)}
                  className="bg-blue-600/50 hover:bg-blue-600 border border-blue-500/50 text-blue-300 hover:text-white disabled:bg-slate-800 disabled:border-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-colors"
                >
                  Export
                </button>
              </div>

              {/* Progress Bar */}
              {ffRunning && (
                <div className="mt-4">
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span>{ffCurrentConfig ? evalConfigs.find(c => c.id === ffCurrentConfig)?.name : 'Starting...'}</span>
                    <span>{Math.round(ffProgress)}%</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-yellow-500 to-orange-500 transition-all duration-300"
                      style={{ width: `${ffProgress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Middle Section: Configurations */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Configurations</h2>
                <div className="flex gap-1 flex-wrap">
                  {([
                    { mode: 'no_memory', label: 'No Memory', color: 'slate', mmQueryType: 'recall' as const },
                    { mode: 'filesystem', label: 'Filesystem', color: 'amber', mmQueryType: 'recall' as const },
                    { mode: 'recall', label: 'Recall', color: 'purple', mmQueryType: 'recall' as const },
                    { mode: 'reflect', label: 'Reflect', color: 'cyan', mmQueryType: 'reflect' as const },
                    { mode: 'hindsight_mm', label: 'MM-Recall', color: 'emerald', mmQueryType: 'recall' as const },
                    { mode: 'hindsight_mm', label: 'MM-Reflect', color: 'green', mmQueryType: 'reflect' as const },
                    { mode: 'hindsight_mm_nowait', label: 'MM-Recall NW', color: 'teal', mmQueryType: 'recall' as const },
                    { mode: 'hindsight_mm_nowait', label: 'MM-Reflect NW', color: 'sky', mmQueryType: 'reflect' as const },
                  ] as const).map(({ mode, label, color, mmQueryType }) => (
                    <button
                      key={`${mode}-${mmQueryType}`}
                      onClick={() => {
                        configCounterRef.current += 1;
                        const configNum = configCounterRef.current;
                        const colorIndex = evalConfigs.length % configColors.length;
                        setEvalConfigs(prev => [...prev, {
                          id: `config-${configNum}`,
                          name: label,
                          model: 'openai/gpt-4o',
                          memoryMode: mode,
                          bankId: `${mode}-${shortId()}`,
                          color: configColors[colorIndex],
                          enabled: true,
                          results: [],
                          query: DEFAULT_QUERY,
                          mission: DEFAULT_MISSION,
                          ...DEFAULT_BENCHMARK_SETTINGS,
                          mmQueryType: mmQueryType,
                        }]);
                      }}
                      disabled={ffRunning}
                      className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-50 disabled:cursor-not-allowed border-${color}-500/50 text-${color}-400 hover:bg-${color}-900/30`}
                    >
                      + {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {evalConfigs.map(config => (
                  <div
                    key={config.id}
                    className={`p-4 rounded-lg border transition-all ${
                      config.enabled
                        ? 'bg-slate-700/50 border-slate-600'
                        : 'bg-slate-800/50 border-slate-700 opacity-60'
                    }`}
                  >
                    {/* Header */}
                    <div className="flex items-center gap-2 mb-3">
                      <input
                        type="checkbox"
                        checked={config.enabled}
                        onChange={(e) => updateEvalConfig(config.id, { enabled: e.target.checked })}
                        disabled={ffRunning}
                        className="w-4 h-4 rounded"
                      />
                      <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: config.color }} />
                      <input
                        type="text"
                        value={config.name}
                        onChange={(e) => updateEvalConfig(config.id, { name: e.target.value })}
                        disabled={ffRunning}
                        className="flex-1 bg-transparent text-slate-300 text-sm font-medium truncate border-b border-transparent hover:border-slate-600 focus:border-blue-500 focus:outline-none px-0.5"
                        placeholder="Config name"
                      />
                      {evalConfigs.length > 1 && (
                        <button
                          onClick={() => removeEvalConfig(config.id)}
                          disabled={ffRunning}
                          className="text-slate-500 hover:text-red-400 disabled:cursor-not-allowed text-sm"
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    {/* Model Selection */}
                    <div className="mb-2">
                      <label className="block text-xs text-slate-500 mb-1">Model</label>
                      <select
                        value={config.model}
                        onChange={(e) => {
                          const newModel = e.target.value;
                          const modelName = modelOptions.find(m => m.id === newModel)?.name || newModel;
                          const modeName = config.memoryMode.charAt(0).toUpperCase() + config.memoryMode.slice(1);
                          updateEvalConfig(config.id, {
                            model: newModel,
                            name: `${modeName} (${modelName})`,
                          });
                        }}
                        disabled={ffRunning}
                        className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300"
                      >
                        {modelOptions.map(m => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                    </div>

                    {/* Agent Mode */}
                    <div className="mb-3">
                      <label className="block text-xs text-slate-500 mb-1">Agent Mode</label>
                      <select
                        value={config.memoryMode}
                        onChange={(e) => {
                          const mode = e.target.value as AgentMode;
                          const modeLabels: Record<AgentMode, string> = {
                            'no_memory': 'No Memory',
                            'filesystem': 'Filesystem',
                            'recall': 'Recall',
                            'reflect': 'Reflect',
                            'hindsight_mm': 'Hindsight MM',
                            'hindsight_mm_nowait': 'MM NoWait',
                          };
                          updateEvalConfig(config.id, {
                            memoryMode: mode,
                            name: modeLabels[mode],
                            bankId: `${mode}-${shortId()}`
                          });
                        }}
                        disabled={ffRunning}
                        className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300"
                      >
                        <option value="no_memory">No Memory (Baseline)</option>
                        <option value="filesystem">Filesystem (Agent Notes)</option>
                        <option value="recall">Recall (Raw Facts)</option>
                        <option value="reflect">Reflect (LLM Synthesis)</option>
                        <option value="hindsight_mm">Hindsight MM (Wait)</option>
                        <option value="hindsight_mm_nowait">MM NoWait</option>
                      </select>
                    </div>

                    {/* Learning Settings */}
                    <div className="mb-3 grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Repeat Ratio</label>
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          value={config.repeatRatio}
                          onChange={(e) => updateEvalConfig(config.id, { repeatRatio: parseFloat(e.target.value) || 0 })}
                          disabled={ffRunning}
                          className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                        />
                      </div>
                      <div className="flex items-end">
                        <label className="flex items-center gap-1 text-xs text-slate-400">
                          <input
                            type="checkbox"
                            checked={config.pairedMode}
                            onChange={(e) => updateEvalConfig(config.id, { pairedMode: e.target.checked })}
                            disabled={ffRunning}
                            className="w-3 h-3 rounded"
                          />
                          Paired (2x each)
                        </label>
                      </div>
                    </div>

                    {/* Step Limits */}
                    <div className="mb-3 grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Step Mult</label>
                        <input
                          type="number"
                          min={1}
                          max={20}
                          step={0.5}
                          value={config.stepMultiplier}
                          onChange={(e) => updateEvalConfig(config.id, { stepMultiplier: parseFloat(e.target.value) || 5 })}
                          disabled={ffRunning}
                          className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                          title="max_steps = optimal * multiplier"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Min Steps</label>
                        <input
                          type="number"
                          min={5}
                          max={50}
                          step={1}
                          value={config.minSteps}
                          onChange={(e) => updateEvalConfig(config.id, { minSteps: parseInt(e.target.value) || 15 })}
                          disabled={ffRunning}
                          className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                          title="Minimum step limit per delivery"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Business</label>
                        <select
                          value={config.includeBusiness}
                          onChange={(e) => updateEvalConfig(config.id, { includeBusiness: e.target.value as 'always' | 'never' | 'random' })}
                          disabled={ffRunning}
                          className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                          title="Include business name in package"
                        >
                          <option value="random">Random</option>
                          <option value="always">Always</option>
                          <option value="never">Never</option>
                        </select>
                      </div>
                    </div>

                    {/* Memory Query Mode - only for hindsight modes */}
                    {config.memoryMode !== 'no_memory' && config.memoryMode !== 'filesystem' && (
                      <div className="mb-3 space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-xs text-slate-500 mb-1">Memory Injection</label>
                            <select
                              value={config.memoryQueryMode}
                              onChange={(e) => updateEvalConfig(config.id, { memoryQueryMode: e.target.value as 'inject_once' | 'per_step' | 'both' })}
                              disabled={ffRunning}
                              className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                            >
                              <option value="inject_once">Once at Start</option>
                              <option value="per_step">Every Step</option>
                              <option value="both">Both</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs text-slate-500 mb-1">Refresh Interval</label>
                            <input
                              type="number"
                              min={0}
                              max={50}
                              step={1}
                              value={config.refreshInterval}
                              onChange={(e) => updateEvalConfig(config.id, { refreshInterval: parseInt(e.target.value) || 0 })}
                              disabled={ffRunning}
                              className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                              title="Refresh mental models every N deliveries (0 = disabled)"
                            />
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <label className="flex items-center gap-1 text-xs text-slate-400">
                            <input
                              type="checkbox"
                              checked={config.waitForConsolidation}
                              onChange={(e) => updateEvalConfig(config.id, { waitForConsolidation: e.target.checked })}
                              disabled={ffRunning}
                              className="w-3 h-3 rounded"
                            />
                            Wait for Consolidation
                          </label>
                        </div>
                        {/* Preseed Coverage */}
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <div>
                            <label className="block text-xs text-slate-500 mb-1">Preseed Coverage</label>
                            <div className="flex items-center gap-2">
                              <input
                                type="range"
                                min={0}
                                max={100}
                                step={10}
                                value={Math.round((config.preseedCoverage || 0) * 100)}
                                onChange={(e) => updateEvalConfig(config.id, { preseedCoverage: parseInt(e.target.value) / 100 })}
                                disabled={ffRunning}
                                className="flex-1 h-1"
                              />
                              <span className="text-xs text-slate-400 w-8">{Math.round((config.preseedCoverage || 0) * 100)}%</span>
                            </div>
                            <p className="text-[10px] text-slate-600 mt-0.5">Pre-seed building knowledge</p>
                          </div>
                          {/* MM Query Type - only for MM modes */}
                          {(config.memoryMode === 'hindsight_mm' || config.memoryMode === 'hindsight_mm_nowait') && (
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">MM Query Type</label>
                              <select
                                value={config.mmQueryType || 'recall'}
                                onChange={(e) => updateEvalConfig(config.id, { mmQueryType: e.target.value as 'recall' | 'reflect' })}
                                disabled={ffRunning}
                                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300"
                              >
                                <option value="recall">Recall (Raw Facts)</option>
                                <option value="reflect">Reflect (LLM Synthesis)</option>
                              </select>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Memory Settings - only for hindsight modes */}
                    {config.memoryMode !== 'no_memory' && config.memoryMode !== 'filesystem' && (
                      <div className="space-y-2 mb-3">
                        {/* Query */}
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">Memory Query</label>
                          <textarea
                            value={config.query}
                            onChange={(e) => updateEvalConfig(config.id, { query: e.target.value })}
                            placeholder={DEFAULT_QUERY}
                            rows={2}
                            disabled={ffRunning}
                            className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300 placeholder-slate-500 resize-none disabled:opacity-50"
                          />
                        </div>
                        {/* Mission */}
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">Bank Mission</label>
                          <textarea
                            value={config.mission}
                            onChange={(e) => updateEvalConfig(config.id, { mission: e.target.value })}
                            placeholder={DEFAULT_MISSION}
                            rows={2}
                            disabled={ffRunning}
                            className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300 placeholder-slate-500 resize-none disabled:opacity-50"
                          />
                        </div>
                        {/* Hindsight URL Override */}
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">
                            Hindsight URL <span className="text-slate-600">(optional override)</span>
                          </label>
                          <input
                            type="text"
                            value={config.hindsightUrl || ''}
                            onChange={(e) => updateEvalConfig(config.id, { hindsightUrl: e.target.value || undefined })}
                            placeholder={globalHindsightUrl}
                            disabled={ffRunning}
                            className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300 placeholder-slate-500 font-mono disabled:opacity-50"
                          />
                        </div>
                      </div>
                    )}

                    {/* Bank ID */}
                    <div className="pt-2 border-t border-slate-600">
                      <label className="block text-xs text-slate-500 mb-1">Bank ID</label>
                      <div className="flex gap-1">
                        <input
                          type="text"
                          value={config.bankId}
                          onChange={(e) => updateEvalConfig(config.id, { bankId: e.target.value })}
                          disabled={ffRunning}
                          className="flex-1 bg-slate-800 border border-slate-600 rounded px-2 py-1 text-[10px] text-slate-400 font-mono disabled:opacity-50"
                        />
                        <button
                          onClick={() => updateEvalConfig(config.id, { bankId: `${config.memoryMode}-${shortId()}` })}
                          disabled={ffRunning}
                          className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-400 text-[10px] rounded disabled:opacity-50"
                          title="Generate new bank ID"
                        >
                          New
                        </button>
                      </div>
                    </div>

                    {/* Results Summary */}
                    {config.results.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-600 grid grid-cols-3 gap-2 text-center">
                        <div>
                          <div className="text-sm font-bold text-slate-300">{config.results.length}</div>
                          <div className="text-[10px] text-slate-500">runs</div>
                        </div>
                        <div>
                          <div className="text-sm font-bold text-green-400">
                            {Math.round(config.results.filter(r => r.success).length / config.results.length * 100)}%
                          </div>
                          <div className="text-[10px] text-slate-500">success</div>
                        </div>
                        <div>
                          <div className="text-sm font-bold text-blue-400">
                            {(config.results.reduce((s, r) => s + r.steps, 0) / config.results.length).toFixed(1)}
                          </div>
                          <div className="text-[10px] text-slate-500">avg steps</div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom Section: Results */}
            {evalConfigs.some(c => c.results.length > 0) && (
              <div className="space-y-6">
                {/* Chart Legend */}
                {chartSettings.enabled && (
                  <div className="flex flex-wrap gap-3 justify-center">
                    {evalConfigs.filter(c => c.results.length > 0).map(config => (
                      <div key={config.id} className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: config.color }} />
                        <span className="text-xs text-slate-400">{config.name}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Charts Grid */}
                {chartSettings.enabled && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Steps Per Delivery Chart */}
                    {chartSettings.stepsPerDelivery && (
                      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                        <h3 className="text-sm font-semibold text-slate-300 mb-3">Steps Per Delivery</h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <LineChart>
                            <XAxis dataKey="delivery" stroke="#64748b" fontSize={10} tickLine={false} type="number" domain={[1, 'auto']} allowDecimals={false} />
                            <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 'auto']} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }} />
                            <ReferenceLine y={3} stroke="#4ade80" strokeDasharray="3 3" label={{ value: 'optimal', position: 'right', fill: '#4ade80', fontSize: 10 }} />
                            {evalConfigs.filter(c => c.results.length > 0).map(config => (
                              <Line key={config.id} data={config.results.map((r, i) => ({ delivery: i + 1, steps: r.steps }))} type="monotone" dataKey="steps" name={config.name} stroke={config.color} strokeWidth={2} dot={{ r: 2, fill: config.color }} />
                            ))}
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* Cumulative Steps Chart */}
                    {chartSettings.cumulativeSteps && (
                      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                        <h3 className="text-sm font-semibold text-slate-300 mb-3">Cumulative Steps</h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <LineChart>
                            <XAxis dataKey="delivery" stroke="#64748b" fontSize={10} tickLine={false} type="number" domain={[1, 'auto']} allowDecimals={false} />
                            <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }} />
                            {evalConfigs.filter(c => c.results.length > 0).map(config => {
                              let cumulative = 0;
                              const data = config.results.map((r, i) => {
                                cumulative += r.steps;
                                return { delivery: i + 1, cumSteps: cumulative };
                              });
                              return <Line key={config.id} data={data} type="monotone" dataKey="cumSteps" name={config.name} stroke={config.color} strokeWidth={2} dot={{ r: 2, fill: config.color }} />;
                            })}
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* Path Efficiency Chart (using steps - lower is better, show as efficiency %) */}
                    {chartSettings.pathEfficiency && (
                      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                        <h3 className="text-sm font-semibold text-slate-300 mb-3">Path Efficiency (optimal=3 steps)</h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <LineChart>
                            <XAxis dataKey="delivery" stroke="#64748b" fontSize={10} tickLine={false} type="number" domain={[1, 'auto']} allowDecimals={false} />
                            <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }} formatter={(value) => [`${value}%`, 'Efficiency']} />
                            <ReferenceLine y={90} stroke="#4ade80" strokeDasharray="3 3" label={{ value: '90%', position: 'right', fill: '#4ade80', fontSize: 10 }} />
                            {evalConfigs.filter(c => c.results.length > 0).map(config => {
                              const data = config.results.map((r, i) => ({
                                delivery: i + 1,
                                efficiency: Math.round(r.pathEfficiency * 100)
                              }));
                              return <Line key={config.id} data={data} type="monotone" dataKey="efficiency" name={config.name} stroke={config.color} strokeWidth={2} dot={{ r: 2, fill: config.color }} />;
                            })}
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* Comparison Summary Bar Chart */}
                    {chartSettings.comparisonSummary && (
                      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                        <h3 className="text-sm font-semibold text-slate-300 mb-3">Performance Summary</h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart data={evalConfigs.filter(c => c.results.length > 0).map(config => ({
                            name: config.name,
                            avgSteps: parseFloat((config.results.reduce((s, r) => s + r.steps, 0) / config.results.length).toFixed(1)),
                            successRate: Math.round(config.results.filter(r => r.success).length / config.results.length * 100),
                            fill: config.color
                          }))}>
                            <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                            <YAxis yAxisId="left" stroke="#64748b" fontSize={10} tickLine={false} />
                            <YAxis yAxisId="right" orientation="right" stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', fontSize: '12px' }} />
                            <Legend wrapperStyle={{ fontSize: '10px' }} />
                            <Bar yAxisId="left" dataKey="avgSteps" name="Avg Steps" fill="#3b82f6" />
                            <Bar yAxisId="right" dataKey="successRate" name="Success %" fill="#22c55e" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}

                {/* Results Table */}
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                  <h2 className="text-lg font-semibold text-slate-300 mb-4">Results Comparison</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-slate-500 text-xs uppercase">
                          <th className="text-left py-2 px-3">Config</th>
                          <th className="text-center py-2 px-3">Runs</th>
                          <th className="text-center py-2 px-3">Success</th>
                          <th className="text-center py-2 px-3">Avg Steps</th>
                          <th className="text-center py-2 px-3">Min</th>
                          <th className="text-center py-2 px-3">Max</th>
                          <th className="text-center py-2 px-3">Efficiency</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evalConfigs.filter(c => c.results.length > 0).map(config => {
                          const successCount = config.results.filter(r => r.success).length;
                          const avgSteps = config.results.reduce((sum, r) => sum + r.steps, 0) / config.results.length;
                          const minSteps = Math.min(...config.results.map(r => r.steps));
                          const maxSteps = Math.max(...config.results.map(r => r.steps));
                          const avgEfficiency = Math.round(config.results.reduce((sum, r) => sum + r.pathEfficiency, 0) / config.results.length * 100);
                          return (
                            <tr key={config.id} className="border-t border-slate-700">
                              <td className="py-2 px-3">
                                <div className="flex items-center gap-2">
                                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
                                  <span className="text-slate-300 text-xs">{config.name}</span>
                                </div>
                              </td>
                              <td className="text-center py-2 px-3 text-slate-400">{config.results.length}</td>
                              <td className="text-center py-2 px-3">
                                <span className={successCount === config.results.length ? 'text-green-400' : 'text-yellow-400'}>
                                  {Math.round(successCount / config.results.length * 100)}%
                                </span>
                              </td>
                              <td className="text-center py-2 px-3 font-mono text-slate-300">{avgSteps.toFixed(1)}</td>
                              <td className="text-center py-2 px-3 font-mono text-green-400">{minSteps}</td>
                              <td className="text-center py-2 px-3 font-mono text-red-400">{maxSteps}</td>
                              <td className="text-center py-2 px-3">
                                <span className={avgEfficiency >= 90 ? 'text-green-400' : avgEfficiency >= 50 ? 'text-yellow-400' : 'text-red-400'}>
                                  {avgEfficiency}%
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  );
}

export default App;
