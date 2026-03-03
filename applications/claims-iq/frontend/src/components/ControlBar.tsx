import type { AgentMode } from '../types.ts';
import { useClaimsStore } from '../stores/claimsStore.ts';

const MODE_LABELS: Record<AgentMode, string> = {
  no_memory: 'No Memory',
  recall: 'Recall',
  reflect: 'Reflect',
  hindsight_mm: 'Mental Models',
};

interface ControlBarProps {
  onProcessClaim: () => void;
  onCancel: () => void;
  onSetMode: (mode: AgentMode) => void;
  onResetMemory: () => void;
  onRefreshModels: () => void;
}

export function ControlBar({ onProcessClaim, onCancel, onSetMode, onResetMemory, onRefreshModels }: ControlBarProps) {
  const { connected, bankId, mode, isProcessing, isRefreshingModels } = useClaimsStore();

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-slate-800/80 border-b border-slate-700">
      <h1 className="text-lg font-bold text-white mr-2">ClaimsIQ</h1>

      <div className="h-5 w-px bg-slate-600" />

      {/* Process / Cancel */}
      {isProcessing ? (
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-sm font-medium rounded bg-red-600 hover:bg-red-700 text-white"
        >
          Cancel
        </button>
      ) : (
        <button
          onClick={onProcessClaim}
          disabled={!connected}
          className="px-3 py-1.5 text-sm font-medium rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
        >
          Process Claim
        </button>
      )}

      <div className="h-5 w-px bg-slate-600" />

      {/* Mode selector */}
      <label className="text-xs text-slate-400">Mode:</label>
      <select
        value={mode}
        onChange={(e) => onSetMode(e.target.value as AgentMode)}
        disabled={isProcessing}
        className="bg-slate-700 text-slate-200 text-sm rounded px-2 py-1 border border-slate-600"
      >
        {Object.entries(MODE_LABELS).map(([value, label]) => (
          <option key={value} value={value}>{label}</option>
        ))}
      </select>

      <div className="flex-1" />

      {/* Bank info & controls */}
      <span className="text-xs text-slate-500">Bank:</span>
      <span className="text-xs text-slate-300 font-mono">{bankId ? bankId.slice(0, 16) : '...'}</span>

      <button
        onClick={onResetMemory}
        disabled={isProcessing}
        className="px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 text-slate-300 border border-slate-600 disabled:opacity-50"
      >
        New Bank
      </button>

      <button
        onClick={onRefreshModels}
        disabled={isProcessing || isRefreshingModels}
        className="px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 text-slate-300 border border-slate-600 disabled:opacity-50"
      >
        {isRefreshingModels ? 'Refreshing...' : 'Refresh Models'}
      </button>

      {/* Connection indicator */}
      <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
    </div>
  );
}
