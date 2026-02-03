import { useState } from 'react';
import type { AgentMode, BenchmarkConfig, AgentModeInfo, BenchmarkPreset } from '../types';

interface BenchmarkSettingsProps {
  config: BenchmarkConfig;
  onChange: (config: Partial<BenchmarkConfig>) => void;
  disabled?: boolean;
}

// Agent mode information
const AGENT_MODES: AgentModeInfo[] = [
  { id: 'no_memory', name: 'No Memory', description: 'Stateless baseline - no memory injection or storage' },
  { id: 'filesystem', name: 'Filesystem', description: 'Agent manages own notes (read_notes/write_notes tools)' },
  { id: 'recall', name: 'Recall', description: 'Hindsight recall - raw fact retrieval' },
  { id: 'reflect', name: 'Reflect', description: 'Hindsight reflect - LLM-synthesized answers' },
  { id: 'hindsight_mm', name: 'Hindsight MM', description: 'Mental models with consolidation wait' },
  { id: 'hindsight_mm_nowait', name: 'MM (No Wait)', description: 'Mental models without waiting' },
];

// Presets
const PRESETS: BenchmarkPreset[] = [
  {
    id: 'quick_test',
    name: 'Quick Test',
    description: '5 deliveries, easy mode',
    config: { mode: 'recall', numDeliveries: 5, difficulty: 'easy' },
  },
  {
    id: 'learning_test',
    name: 'Learning Test',
    description: '20 deliveries, 50% repeat',
    config: { mode: 'hindsight_mm', numDeliveries: 20, repeatRatio: 0.5, difficulty: 'easy' },
  },
  {
    id: 'paired',
    name: 'Paired Mode',
    description: 'Each office visited 2x',
    config: { mode: 'hindsight_mm', numDeliveries: 12, pairedMode: true, difficulty: 'easy' },
  },
  {
    id: 'full',
    name: 'Full Benchmark',
    description: '30 deliveries, medium',
    config: { mode: 'hindsight_mm', numDeliveries: 30, difficulty: 'medium' },
  },
  {
    id: 'baseline',
    name: 'No Memory Baseline',
    description: 'Stateless comparison',
    config: { mode: 'no_memory', numDeliveries: 10, difficulty: 'easy' },
  },
];

export function BenchmarkSettings({ config, onChange, disabled = false }: BenchmarkSettingsProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleModeChange = (mode: AgentMode) => {
    onChange({ mode });
  };

  const handlePresetClick = (preset: BenchmarkPreset) => {
    onChange(preset.config);
  };

  // Is mental model mode?
  const isMentalModelMode = config.mode === 'hindsight_mm' || config.mode === 'hindsight_mm_nowait';

  return (
    <div className="space-y-4">
      {/* Presets */}
      <div>
        <label className="block text-xs text-slate-500 mb-2">Quick Presets</label>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map(preset => (
            <button
              key={preset.id}
              onClick={() => handlePresetClick(preset)}
              disabled={disabled}
              title={preset.description}
              className="px-2 py-1 text-xs rounded border border-slate-600 text-slate-400 hover:bg-slate-700 hover:text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {preset.name}
            </button>
          ))}
        </div>
      </div>

      {/* Agent Mode */}
      <div>
        <label className="block text-xs text-slate-500 mb-2">Agent Mode</label>
        <div className="grid grid-cols-3 gap-2">
          {AGENT_MODES.map(mode => (
            <button
              key={mode.id}
              onClick={() => handleModeChange(mode.id)}
              disabled={disabled}
              title={mode.description}
              className={`px-2 py-1.5 text-xs rounded border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                config.mode === mode.id
                  ? mode.id === 'no_memory' ? 'bg-slate-600 text-white border-slate-500'
                    : mode.id === 'filesystem' ? 'bg-amber-600 text-white border-amber-500'
                    : mode.id === 'recall' ? 'bg-purple-600 text-white border-purple-500'
                    : mode.id === 'reflect' ? 'bg-cyan-600 text-white border-cyan-500'
                    : 'bg-emerald-600 text-white border-emerald-500'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
              }`}
            >
              {mode.name}
            </button>
          ))}
        </div>
      </div>

      {/* Basic Settings */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Deliveries</label>
          <input
            type="number"
            min={1}
            max={100}
            value={config.numDeliveries}
            onChange={(e) => onChange({ numDeliveries: parseInt(e.target.value) || 10 })}
            disabled={disabled}
            className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Difficulty</label>
          <select
            value={config.difficulty}
            onChange={(e) => onChange({ difficulty: e.target.value })}
            disabled={disabled}
            className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
          >
            <option value="easy">Easy (3 floors, 6 offices)</option>
            <option value="medium">Medium (3 buildings)</option>
            <option value="hard">Hard (City grid)</option>
          </select>
        </div>
      </div>

      {/* Repeat Settings */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Repeat Ratio: {Math.round(config.repeatRatio * 100)}%
          </label>
          <input
            type="range"
            min={0}
            max={100}
            value={config.repeatRatio * 100}
            onChange={(e) => onChange({ repeatRatio: parseInt(e.target.value) / 100 })}
            disabled={disabled || config.pairedMode}
            className="w-full disabled:opacity-50"
          />
        </div>
        <div className="flex items-center gap-2 pt-5">
          <input
            type="checkbox"
            id="pairedMode"
            checked={config.pairedMode}
            onChange={(e) => onChange({ pairedMode: e.target.checked })}
            disabled={disabled}
            className="w-4 h-4 rounded disabled:opacity-50"
          />
          <label htmlFor="pairedMode" className="text-xs text-slate-400">
            Paired Mode (each office 2x)
          </label>
        </div>
      </div>

      {/* Mental Model Settings */}
      {isMentalModelMode && (
        <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-lg p-3">
          <label className="block text-xs text-emerald-400 mb-2">Mental Model Settings</label>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Refresh Every N Deliveries</label>
              <select
                value={config.refreshInterval}
                onChange={(e) => onChange({ refreshInterval: parseInt(e.target.value) })}
                disabled={disabled}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
              >
                <option value={0}>Off (Manual)</option>
                <option value={1}>Every 1</option>
                <option value={3}>Every 3</option>
                <option value={5}>Every 5</option>
                <option value={10}>Every 10</option>
              </select>
            </div>
            <div className="flex items-center gap-2 pt-5">
              <input
                type="checkbox"
                id="waitConsolidation"
                checked={config.waitForConsolidation}
                onChange={(e) => onChange({ waitForConsolidation: e.target.checked })}
                disabled={disabled || config.mode === 'hindsight_mm_nowait'}
                className="w-4 h-4 rounded disabled:opacity-50"
              />
              <label htmlFor="waitConsolidation" className="text-xs text-slate-400">
                Wait for consolidation
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Advanced Toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-xs text-slate-500 hover:text-slate-400 transition-colors"
      >
        {showAdvanced ? '▼ Hide Advanced' : '▶ Show Advanced'}
      </button>

      {/* Advanced Settings */}
      {showAdvanced && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Step Multiplier</label>
              <input
                type="number"
                min={1}
                max={20}
                step={0.5}
                value={config.stepMultiplier}
                onChange={(e) => onChange({ stepMultiplier: parseFloat(e.target.value) || 5.0 })}
                disabled={disabled}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-600">max_steps = optimal × multiplier</span>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Min Steps</label>
              <input
                type="number"
                min={5}
                max={100}
                value={config.minSteps}
                onChange={(e) => onChange({ minSteps: parseInt(e.target.value) || 15 })}
                disabled={disabled}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Include Business Name</label>
              <select
                value={config.includeBusiness}
                onChange={(e) => onChange({ includeBusiness: e.target.value as 'always' | 'never' | 'random' })}
                disabled={disabled}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
              >
                <option value="random">Random</option>
                <option value="always">Always</option>
                <option value="never">Never</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Memory Query Mode</label>
              <select
                value={config.memoryQueryMode}
                onChange={(e) => onChange({ memoryQueryMode: e.target.value as 'inject_once' | 'per_step' | 'both' })}
                disabled={disabled || config.mode === 'no_memory' || config.mode === 'filesystem'}
                className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-50"
              >
                <option value="inject_once">Inject Once (at start)</option>
                <option value="per_step">Per Step (remember tool)</option>
                <option value="both">Both</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Random Seed (optional)</label>
            <input
              type="number"
              placeholder="Leave empty for random"
              value={config.seed ?? ''}
              onChange={(e) => onChange({ seed: e.target.value ? parseInt(e.target.value) : undefined })}
              disabled={disabled}
              className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-300 placeholder:text-slate-600 disabled:opacity-50"
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Default config for creating new benchmarks
export const DEFAULT_BENCHMARK_CONFIG: BenchmarkConfig = {
  mode: 'recall',
  model: 'openai/gpt-4o',
  numDeliveries: 10,
  repeatRatio: 0.4,
  pairedMode: false,
  includeBusiness: 'random',
  stepMultiplier: 5.0,
  minSteps: 15,
  memoryQueryMode: 'inject_once',
  waitForConsolidation: true,
  refreshInterval: 5,
  difficulty: 'easy',
};
