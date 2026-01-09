import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useGameStore } from './stores/gameStore';
import { PhaserGame } from './game/PhaserGame';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
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
  } = useGameStore();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedRecipient, setSelectedRecipient] = useState<string>('');
  const [expandedAction, setExpandedAction] = useState<number | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);
  const [buildingInfo, setBuildingInfo] = useState<BuildingInfo | null>(null);
  const [showDemoSettings, setShowDemoSettings] = useState(false);
  const [showBuildingLayout, setShowBuildingLayout] = useState(false);
  const [selectedModel, setSelectedModel] = useState('openai/gpt-4o-mini');

  // Hindsight settings
  const [hindsightInject, setHindsightInject] = useState(true);
  const [hindsightReflect, setHindsightReflect] = useState(false);
  const [hindsightStore, setHindsightStore] = useState(true);

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
  type MemoryMode = 'baseline' | 'recall' | 'reflect';
  const [memoryMode, setMemoryMode] = useState<MemoryMode>('recall');

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

  // View mode state (UI vs Fast-Forward)
  const [viewMode, setViewMode] = useState<'ui' | 'ff'>('ui');

  // Evaluation configuration type
  interface EvalResult {
    success: boolean;
    steps: number;
    recipientName: string;
    deliveryNumber: number;
    actions?: {
      step: number;
      tool: string;
      args: Record<string, unknown>;
      result: string;
      timing: number;
      memoryCount: number;
    }[];
  }

  interface EvalConfig {
    id: string;
    name: string;
    model: string;
    memoryMode: 'baseline' | 'recall' | 'reflect';
    bankId: string;
    color: string;
    enabled: boolean;
    results: EvalResult[];
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

  // Evaluation configs state
  const [evalConfigs, setEvalConfigs] = useState<EvalConfig[]>(() => [
    {
      id: 'baseline-gpt4o-mini',
      name: 'Baseline (GPT-4o Mini)',
      model: 'openai/gpt-4o-mini',
      memoryMode: 'baseline',
      bankId: `baseline-${Math.random().toString(36).slice(2, 8)}`,
      color: configColors[0],
      enabled: true,
      results: [],
    },
    {
      id: 'recall-gpt4o-mini',
      name: 'Recall (GPT-4o Mini)',
      model: 'openai/gpt-4o-mini',
      memoryMode: 'recall',
      bankId: `recall-${Math.random().toString(36).slice(2, 8)}`,
      color: configColors[4],
      enabled: true,
      results: [],
    },
  ]);

  // Fast-forward state
  const [ffLoopCount, setFfLoopCount] = useState(10);
  const [ffRunning, setFfRunning] = useState(false);
  const [ffProgress, setFfProgress] = useState(0);
  const [ffCurrentConfig, setFfCurrentConfig] = useState<string | null>(null);
  const [saveAllSteps, setSaveAllSteps] = useState(false);
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
    const newConfig: EvalConfig = {
      id: configId,
      name: `${modeName} (${modelName})`,
      model,
      memoryMode: mode,
      bankId: `${mode}-${shortId()}`,
      color: configColors[colorIndex],
      enabled: true,
      results: [],
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
  const currentUiBankId = useMemo(() => {
    if (currentUiConfig) return currentUiConfig.bankId;
    return `ui-${selectedModel}-${memoryMode}-${Date.now()}`;
  }, [currentUiConfig, selectedModel, memoryMode]);

  // Fetch employees, demo config, and building info on mount
  useEffect(() => {
    fetch('/api/building/employees')
      .then(res => res.json())
      .then(data => setEmployees(data.employees))
      .catch(console.error);

    fetch('/api/demo-config')
      .then(res => res.json())
      .then(data => setDemoConfig(data))
      .catch(console.error);

    fetch('/api/building')
      .then(res => res.json())
      .then(data => setBuildingInfo(data))
      .catch(console.error);
  }, []);

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
    };
  }, [getOrCreateUiConfig, selectedModel, memoryMode, hindsightInject, hindsightReflect, hindsightStore]);

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
    setUiConfigs(prev => prev.map(c => {
      if (c.id === configId) {
        return {
          ...c,
          results: [...c.results, {
            success,
            steps,
            recipientName,
            deliveryNumber: c.results.length + 1,
          }],
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
    }
  };

  // Reset demo - generates fresh bank IDs for all configs
  const handleResetDemo = () => {
    if (confirm('This will reset all memory banks to fresh state and clear results. Continue?')) {
      // Reset UI mode configs with new bank IDs
      setUiConfigs([]);
      lastHistoryLength.current = 0;
      resetHistory();

      // Reset FF mode configs with new bank IDs
      setEvalConfigs(prev => prev.map(c => ({
        ...c,
        bankId: `${c.memoryMode}-${shortId()}`,
        results: [],
      })));
    }
  };

  // Helper to get hindsight settings for a memory mode
  const getHindsightForMode = (mode: 'baseline' | 'recall' | 'reflect') => {
    const preset = hindsightPresets.find(p => p.id === mode);
    return preset ? { inject: preset.inject, reflect: preset.reflect, store: preset.store } : { inject: false, reflect: false, store: false };
  };

  // Fast-forward handlers - runs all enabled configs IN PARALLEL
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
        const res = await fetch('/api/delivery/fast', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            includeBusiness,
            maxSteps: maxSteps || 150,
            model: config.model,
            hindsight: {
              inject: hs.inject,
              reflect: hs.reflect,
              store: hs.store,
              bankId: config.bankId,
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
              recipientName: result.recipientName || 'Unknown',
              deliveryNumber: deliveryNum,
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
        console.error('Fast-forward error:', err);
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
  }, [evalConfigs, includeBusiness, maxSteps, saveAllSteps]);

  // Add a new config
  const addEvalConfig = useCallback(() => {
    const newId = `config-${shortId()}`;
    const colorIndex = evalConfigs.length % configColors.length;
    setEvalConfigs(prev => [...prev, {
      id: newId,
      name: 'Recall (GPT-4o Mini)',
      model: 'openai/gpt-4o-mini',
      memoryMode: 'recall',
      bankId: `recall-${shortId()}`,
      color: configColors[colorIndex],
      enabled: true,
      results: [],
    }]);
  }, [evalConfigs.length]);

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
          <div>
            <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-blue-400 font-mono">
              DELIVERY AGENT DEMO
            </h1>
            <p className="text-slate-500 text-sm">
              AI agent learning with Hindsight memory
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={handleResetDemo}
              className="text-xs bg-slate-700 hover:bg-slate-600 border border-slate-600 text-slate-300 px-3 py-1.5 rounded transition-colors"
            >
              Reset Demo
            </button>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                connected ? 'bg-green-500 shadow-lg shadow-green-500/50' :
                isConnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="text-sm text-slate-400">
                {connected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
              </span>
            </div>
            {/* Show current bank ID in UI mode only (FF mode shows per-config) */}
            {viewMode === 'ui' && currentUiBankId && (
              <code className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">
                {currentUiBankId}
              </code>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 max-w-7xl mx-auto">
        {/* View Mode Tabs */}
        <div className="mb-6">
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
              onClick={() => setViewMode('ff')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                viewMode === 'ff'
                  ? 'bg-gradient-to-r from-yellow-600 to-orange-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Fast-Forward
            </button>
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

          {showDemoSettings && (
            <div className="mt-3 bg-slate-800/50 rounded-xl p-4 border border-slate-700 space-y-4">
              {/* Model Selection - UI mode only */}
              {viewMode === 'ui' && (
                <div>
                  <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-3">Agent Model</h3>
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
                    </div>
                  </div>

                  {/* User Prompt */}
                  <div>
                    <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">User Prompt</h3>
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                      <code className="text-blue-400 text-sm font-mono whitespace-pre-wrap">
                        Please deliver this package: Package #{"<id>"}: To {"<recipient_name>"} [at {"<business_name>"}]
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

                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Inject Memories</span>
                      <span className={hindsightInject ? 'text-green-400' : 'text-slate-500'}>
                        {hindsightInject ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Use Reflect</span>
                      <span className={hindsightReflect ? 'text-green-400' : 'text-slate-500'}>
                        {hindsightReflect ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Store Deliveries</span>
                      <span className={hindsightStore ? 'text-green-400' : 'text-slate-500'}>
                        {hindsightStore ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    {demoConfig && (
                      <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-700">
                        <span className="text-slate-400">API URL</span>
                        <code className="text-purple-400 font-mono text-xs">{demoConfig.hindsight.apiUrl}</code>
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
                isThinking={isThinking && !isAnimating}
                packageText={currentPackage ? `${currentPackage.recipientName}${currentPackage.businessName ? ` @ ${currentPackage.businessName}` : ''}` : ''}
                deliverySuccess={deliveryStatus === 'success'}
                deliveryFailed={deliveryStatus === 'failed'}
                lastActionTool={actions.length > 0 ? actions[actions.length - 1].toolName : undefined}
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
                      F{emp.floor} {emp.side} | {emp.business} | {emp.name}
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

        {/* Fast-Forward Mode */}
        {viewMode === 'ff' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Chart & Controls */}
            <div className="lg:col-span-2 space-y-4">
              {/* Run Controls */}
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <h2 className="text-lg font-semibold text-slate-300 mb-4">Evaluation Run</h2>
                <p className="text-slate-500 text-sm mb-4">
                  Run deliveries across all enabled configurations to compare performance.
                </p>

                <div className="grid grid-cols-2 gap-4 mb-4">
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
                </div>

                <label className="flex items-center gap-3 cursor-pointer group mb-2">
                  <input
                    type="checkbox"
                    checked={includeBusiness}
                    onChange={(e) => setIncludeBusiness(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-yellow-500 focus:ring-yellow-500 focus:ring-offset-0"
                    disabled={ffRunning}
                  />
                  <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                    Include business name in prompt
                  </span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group mb-4">
                  <input
                    type="checkbox"
                    checked={saveAllSteps}
                    onChange={(e) => setSaveAllSteps(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                    disabled={ffRunning}
                  />
                  <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                    Save all steps (detailed logs for export)
                  </span>
                </label>

                <div className="flex gap-2">
                  <button
                    onClick={() => runFastForward(ffLoopCount)}
                    disabled={ffRunning || evalConfigs.filter(c => c.enabled).length === 0}
                    className="flex-1 bg-gradient-to-r from-yellow-600 to-orange-500 hover:from-yellow-500 hover:to-orange-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-yellow-500/20 disabled:shadow-none"
                  >
                    {ffRunning ? `Running ${ffCurrentConfig ? evalConfigs.find(c => c.id === ffCurrentConfig)?.name : ''}...` : `Run ${ffLoopCount} x ${evalConfigs.filter(c => c.enabled).length} configs`}
                  </button>
                  <button
                    onClick={stopFastForward}
                    disabled={!ffRunning}
                    className="bg-red-600/80 hover:bg-red-600 disabled:bg-slate-600/50 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-colors"
                  >
                    Stop
                  </button>
                </div>

                {/* Progress Bar */}
                {ffRunning && (
                  <div className="mt-4">
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>Progress</span>
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

              {/* Multi-Series Learning Curve Chart */}
              {evalConfigs.some(c => c.results.length >= 2) && (
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-slate-300">Learning Curves</h2>
                    {/* Legend */}
                    <div className="flex flex-wrap gap-3">
                      {evalConfigs.filter(c => c.results.length > 0).map(config => (
                        <div key={config.id} className="flex items-center gap-1.5">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: config.color }} />
                          <span className="text-xs text-slate-400">{config.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <ResponsiveContainer width="100%" height={250}>
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
                      <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 'auto']} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #475569',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <ReferenceLine y={3} stroke="#4ade80" strokeDasharray="3 3" />
                      {evalConfigs.filter(c => c.results.length > 0).map(config => (
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
                </div>
              )}

              {/* Stats Comparison Table */}
              {evalConfigs.some(c => c.results.length > 0) && (
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
                        </tr>
                      </thead>
                      <tbody>
                        {evalConfigs.filter(c => c.results.length > 0).map(config => {
                          const successCount = config.results.filter(r => r.success).length;
                          const avgSteps = config.results.reduce((sum, r) => sum + r.steps, 0) / config.results.length;
                          const minSteps = Math.min(...config.results.map(r => r.steps));
                          const maxSteps = Math.max(...config.results.map(r => r.steps));
                          return (
                            <tr key={config.id} className="border-t border-slate-700">
                              <td className="py-2 px-3">
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: config.color }} />
                                  <span className="text-slate-300">{config.name}</span>
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
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column - Config Management */}
            <div className="space-y-4">
              {/* Configurations */}
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-slate-300">Configurations</h2>
                  <button
                    onClick={addEvalConfig}
                    disabled={ffRunning}
                    className="text-xs bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed px-2 py-1 rounded text-slate-300"
                  >
                    + Add
                  </button>
                </div>

                <div className="space-y-3">
                  {evalConfigs.map(config => (
                    <div
                      key={config.id}
                      className={`p-3 rounded-lg border transition-all ${
                        config.enabled
                          ? 'bg-slate-700/50 border-slate-600'
                          : 'bg-slate-800/50 border-slate-700 opacity-60'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <input
                          type="checkbox"
                          checked={config.enabled}
                          onChange={(e) => updateEvalConfig(config.id, { enabled: e.target.checked })}
                          disabled={ffRunning}
                          className="w-4 h-4 rounded"
                        />
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: config.color }} />
                        <span className="flex-1 text-slate-300 text-sm font-medium truncate">
                          {config.name}
                        </span>
                        {evalConfigs.length > 1 && (
                          <button
                            onClick={() => removeEvalConfig(config.id)}
                            disabled={ffRunning}
                            className="text-slate-500 hover:text-red-400 disabled:cursor-not-allowed text-xs"
                          >
                            ✕
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs">
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
                          className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-slate-300"
                        >
                          {modelOptions.map(m => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                          ))}
                        </select>
                        <select
                          value={config.memoryMode}
                          onChange={(e) => {
                            const newMode = e.target.value as 'baseline' | 'recall' | 'reflect';
                            const modelName = modelOptions.find(m => m.id === config.model)?.name || config.model;
                            const modeName = newMode.charAt(0).toUpperCase() + newMode.slice(1);
                            updateEvalConfig(config.id, {
                              memoryMode: newMode,
                              name: `${modeName} (${modelName})`,
                              bankId: `${newMode}-${shortId()}`
                            });
                          }}
                          disabled={ffRunning}
                          className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-slate-300"
                        >
                          <option value="baseline">Baseline</option>
                          <option value="recall">Recall</option>
                          <option value="reflect">Reflect</option>
                        </select>
                      </div>

                      {/* Bank ID */}
                      <div className="mt-2 pt-2 border-t border-slate-600">
                        <code className="text-[10px] text-slate-500 font-mono">{config.bankId}</code>
                      </div>

                      {config.results.length > 0 && (
                        <div className="mt-1 flex justify-between text-xs text-slate-500">
                          <span>{config.results.length} runs</span>
                          <span>Avg: {(config.results.reduce((s, r) => s + r.steps, 0) / config.results.length).toFixed(1)} steps</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Clear Results & Export */}
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={clearAllResults}
                    disabled={ffRunning || !evalConfigs.some(c => c.results.length > 0)}
                    className="flex-1 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-400 hover:text-slate-300 disabled:bg-slate-800 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm transition-colors"
                  >
                    Clear Results
                  </button>
                  <button
                    onClick={exportResults}
                    disabled={!evalConfigs.some(c => c.results.length > 0)}
                    className="flex-1 bg-blue-600/50 hover:bg-blue-600 border border-blue-500/50 text-blue-300 hover:text-white disabled:bg-slate-800 disabled:border-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm transition-colors"
                  >
                    Export JSON
                  </button>
                </div>
              </div>

              {/* Quick Add Presets */}
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <h2 className="text-sm font-semibold text-slate-400 mb-3">Quick Add</h2>
                <div className="grid grid-cols-1 gap-2">
                  {['baseline', 'recall', 'reflect'].map(mode => (
                    <button
                      key={mode}
                      onClick={() => {
                        const newId = `${mode}-${shortId()}`;
                        const colorIndex = evalConfigs.length % configColors.length;
                        setEvalConfigs(prev => [...prev, {
                          id: newId,
                          name: `${mode.charAt(0).toUpperCase() + mode.slice(1)} (GPT-4o Mini)`,
                          model: 'openai/gpt-4o-mini',
                          memoryMode: mode as 'baseline' | 'recall' | 'reflect',
                          bankId: `${mode}-${shortId()}`,
                          color: configColors[colorIndex],
                          enabled: true,
                          results: [],
                        }]);
                      }}
                      disabled={ffRunning}
                      className="text-left text-xs bg-slate-700/50 hover:bg-slate-700 disabled:bg-slate-800 disabled:cursor-not-allowed px-3 py-2 rounded border border-slate-600 text-slate-400"
                    >
                      + Add {mode.charAt(0).toUpperCase() + mode.slice(1)} config
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

export default App;
