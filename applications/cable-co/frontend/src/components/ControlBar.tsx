import { useState } from 'react';
import type { AgentMode } from '../types.ts';
import { useSessionStore } from '../stores/sessionStore.ts';

const MODE_LABELS: Record<AgentMode, string> = {
  memory_off: 'Memory Off',
  memory_on: 'Memory On',
};

interface ControlBarProps {
  onProcessNext: () => void;
  onCancel: () => void;
  onSetMode: (mode: AgentMode) => void;
  onReset: () => void;
  onRefreshModels: () => void;
}

export function ControlBar({ onProcessNext, onCancel, onSetMode, onReset, onRefreshModels }: ControlBarProps) {
  const { connected, bankId, mode, isProcessing, isRefreshingModels, scenariosProcessed, totalScenarios } = useSessionStore();
  const [showResetDialog, setShowResetDialog] = useState(false);

  const allDone = scenariosProcessed >= totalScenarios;

  return (
    <>
      <div className="flex items-center gap-3 px-4 py-2.5 bg-gray-900 border-b border-gray-800">
        <h1 className="text-sm font-bold text-white">CableConnect</h1>
        <span className="text-xs text-gray-600">CSR Workstation</span>

        <div className="h-4 w-px bg-gray-700" />

        {isProcessing ? (
          <button
            onClick={onCancel}
            className="px-3 py-1 text-xs font-medium rounded-md bg-red-600 hover:bg-red-700 text-white"
          >
            Cancel
          </button>
        ) : (
          <button
            onClick={onProcessNext}
            disabled={!connected || allDone}
            className="px-3 py-1 text-xs font-medium rounded-md bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50"
          >
            {allDone ? 'All Done' : 'Next Customer'}
          </button>
        )}

        <span className="text-xs text-gray-500">
          {scenariosProcessed}/{totalScenarios}
        </span>

        <div className="h-4 w-px bg-gray-700" />

        <label className="text-xs text-gray-500">Mode:</label>
        <select
          value={mode}
          onChange={(e) => onSetMode(e.target.value as AgentMode)}
          disabled={isProcessing}
          className="bg-gray-800 text-gray-300 text-xs rounded-md px-2 py-1 border border-gray-700"
        >
          {Object.entries(MODE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>

        <div className="flex-1" />

        <span className="text-xs text-gray-600">Bank:</span>
        <button
          onClick={() => { if (bankId) navigator.clipboard.writeText(bankId); }}
          title="Click to copy full bank ID"
          className="text-xs text-gray-400 font-mono hover:text-gray-200 transition-colors cursor-pointer"
        >
          {bankId ? bankId.slice(0, 12) : '...'}
        </button>

        <button
          onClick={() => setShowResetDialog(true)}
          disabled={isProcessing}
          className="px-2 py-1 text-xs rounded-md bg-gray-800 hover:bg-gray-700 text-gray-400 border border-gray-700 disabled:opacity-50"
        >
          Reset
        </button>

        <button
          onClick={onRefreshModels}
          disabled={isProcessing || isRefreshingModels}
          className="px-2 py-1 text-xs rounded-md bg-gray-800 hover:bg-gray-700 text-gray-400 border border-gray-700 disabled:opacity-50"
        >
          {isRefreshingModels ? 'Refreshing...' : 'Refresh Models'}
        </button>

        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500'}`} />
      </div>

      {showResetDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowResetDialog(false)} />
          <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl px-6 py-5 max-w-sm w-full mx-4">
            <h3 className="text-sm font-semibold text-white mb-2">Reset Memory</h3>
            <p className="text-xs text-gray-400 leading-relaxed mb-5">
              This will delete all stored memories and learned policies from the memory bank and start fresh. This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowResetDialog(false)}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => { setShowResetDialog(false); onReset(); }}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
              >
                Delete All Memories
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
