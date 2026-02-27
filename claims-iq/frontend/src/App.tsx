import { useEffect, useCallback, useState } from 'react';
import { useClaimsStore } from './stores/claimsStore.ts';
import { useWebSocket } from './hooks/useWebSocket.ts';
import { useToast } from './hooks/useToast.ts';
import { ControlBar } from './components/ControlBar.tsx';
import { Pipeline } from './components/Pipeline.tsx';
import { ClaimCard } from './components/ClaimCard.tsx';
import { ActivityLog } from './components/ActivityLog.tsx';
import { MetricsPanel } from './components/MetricsPanel.tsx';
import { MentalModelsPanel } from './components/MentalModelsPanel.tsx';
import { ToastContainer } from './components/ToastContainer.tsx';

function DemoGuide() {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) {
    return (
      <button
        onClick={() => setDismissed(false)}
        className="absolute top-14 right-3 z-10 w-6 h-6 rounded-full bg-blue-600/80 text-white text-xs font-bold hover:bg-blue-500 transition-colors flex items-center justify-center"
        title="Show demo guide"
      >
        ?
      </button>
    );
  }

  return (
    <div className="bg-blue-950/60 border-b border-blue-500/30 px-4 py-2.5 text-xs text-blue-200 flex items-start gap-3">
      <div className="flex-1 space-y-1">
        <p className="font-semibold text-blue-100">What to watch for:</p>
        <ul className="space-y-0.5 text-blue-300/90">
          <li>The agent starts with <span className="text-blue-100 font-medium">NO knowledge</span> of coverage rules, escalation thresholds, or the correct workflow.</li>
          <li>Watch the Activity Log for <span className="text-red-300 font-medium">REJECTED</span> cards — these are mistakes the agent is learning from.</li>
          <li>In memory modes, past mistakes are <span className="text-purple-300 font-medium">recalled</span> before processing new claims.</li>
          <li>The Performance panel shows accuracy and rework rates improving over time.</li>
        </ul>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-blue-400 hover:text-blue-200 text-sm mt-0.5 flex-shrink-0"
      >
        {'\u2715'}
      </button>
    </div>
  );
}

function App() {
  const { toasts, showError, showInfo, dismiss } = useToast();

  const {
    currentClaim,
    currentStage,
    isProcessing,
    isThinking,
    actions,
    memoryInjection,
    claimsProcessed,
    correctDecisions,
    totalSteps,
    totalRework,
    history,
    isStoringMemory,
    isRefreshingModels,
    mentalModels,
    setMentalModels,
  } = useClaimsStore();

  const { processClaim, cancelClaim, resetMemory, setMode } = useWebSocket(showError);

  // Fetch mental models periodically
  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch('/api/memory/mental-models');
      if (res.ok) {
        const data = await res.json();
        setMentalModels(data.models ?? []);
      }
    } catch {
      // silently ignore
    }
  }, [setMentalModels]);

  useEffect(() => {
    fetchModels();
    const interval = setInterval(fetchModels, 10_000);
    return () => clearInterval(interval);
  }, [fetchModels]);

  // Refresh after claim resolved
  useEffect(() => {
    if (!isProcessing && claimsProcessed > 0) {
      fetchModels();
    }
  }, [isProcessing, claimsProcessed, fetchModels]);

  const handleRefreshModels = useCallback(async () => {
    try {
      showInfo('Refreshing mental models...');
      await fetch('/api/memory/mental-models/refresh', { method: 'POST' });
      await fetchModels();
    } catch {
      showError('Failed to refresh models');
    }
  }, [fetchModels, showInfo, showError]);

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <ControlBar
        onProcessClaim={() => processClaim()}
        onCancel={cancelClaim}
        onSetMode={setMode}
        onResetMemory={resetMemory}
        onRefreshModels={handleRefreshModels}
      />

      {/* Demo Guide */}
      <DemoGuide />

      {/* Pipeline */}
      <Pipeline currentStage={currentStage} isProcessing={isProcessing} currentStep={isProcessing ? actions.length : undefined} />

      {/* Main content: 3-column layout */}
      <div className="flex-1 flex gap-3 p-3 min-h-0">
        {/* Left: Claim Card */}
        <div className="w-72 flex-shrink-0">
          <ClaimCard
            claim={currentClaim}
            stage={currentStage}
            result={currentStage === 'resolved' && history.length > 0 ? history[history.length - 1] : undefined}
          />
        </div>

        {/* Center: Activity Log */}
        <div className="flex-1 min-w-0">
          <ActivityLog
            actions={actions}
            memoryInjection={memoryInjection}
            isThinking={isThinking}
            isStoringMemory={isStoringMemory}
            result={currentStage === 'resolved' && history.length > 0 ? history[history.length - 1] : undefined}
          />
        </div>

        {/* Right: Metrics + Mental Models */}
        <div className="w-64 flex-shrink-0 space-y-3 overflow-y-auto">
          <MetricsPanel
            claimsProcessed={claimsProcessed}
            correctDecisions={correctDecisions}
            totalSteps={totalSteps}
            totalRework={totalRework}
            history={history}
          />
          <MentalModelsPanel
            models={mentalModels}
            isRefreshing={isRefreshingModels}
          />
        </div>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}

export default App;
