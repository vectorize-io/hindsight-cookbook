import { useEffect, useCallback } from 'react';
import { useSessionStore } from './stores/sessionStore.ts';
import { useWebSocket } from './hooks/useWebSocket.ts';
import { useToast } from './hooks/useToast.ts';
import { ControlBar } from './components/ControlBar.tsx';
import { CustomerChat } from './components/CustomerChat.tsx';
import { CopilotChat } from './components/CopilotChat.tsx';
import { KnowledgePanel } from './components/KnowledgePanel.tsx';
import { MentalModelsPanel } from './components/MentalModelsPanel.tsx';
import { ToastContainer } from './components/ToastContainer.tsx';

function App() {
  const { toasts, showError, showInfo, dismiss } = useToast();

  const {
    currentScenario,
    isProcessing,
    isThinking,
    actions,
    pendingSuggestion,
    memoryRecall,
    knowledgeRules,
    mode,
    isStoringMemory,
    isRefreshingModels,
    mentalModels,
    setMentalModels,
    history,
    sentResponses,
    csrMessages,
    customerReplies,
  } = useSessionStore();

  const { processNext, cancel, resetMemory, setMode, csrRespond, sendCsrMessage } = useWebSocket(showError);

  const handleApprove = useCallback((suggestionId: string) => {
    csrRespond(suggestionId, true, '');
  }, [csrRespond]);

  const handleReject = useCallback((suggestionId: string, feedback: string) => {
    csrRespond(suggestionId, false, feedback);
  }, [csrRespond]);

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

  useEffect(() => {
    if (!isProcessing && history.length > 0) {
      fetchModels();
    }
  }, [isProcessing, history.length, fetchModels]);

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
    <div className="h-screen flex flex-col bg-gray-950">
      <ControlBar
        onProcessNext={processNext}
        onCancel={cancel}
        onSetMode={setMode}
        onReset={resetMemory}
        onRefreshModels={handleRefreshModels}
      />

      <div className="flex-1 flex min-h-0">
        {/* Left: Customer Chat */}
        <div className="w-1/2 border-r border-gray-800">
          <CustomerChat
            scenario={currentScenario}
            sentResponses={sentResponses}
            customerReplies={customerReplies}
          />
        </div>

        {/* Right: Copilot + Knowledge */}
        <div className="w-1/2 flex flex-col min-h-0">
          {/* Copilot chat — takes most of the space */}
          <div className="flex-1 min-h-0">
            <CopilotChat
              actions={actions}
              pendingSuggestion={pendingSuggestion}
              memoryRecall={memoryRecall}
              csrMessages={csrMessages}
              isThinking={isThinking}
              isStoringMemory={isStoringMemory}
              isProcessing={isProcessing}
              onApprove={handleApprove}
              onReject={handleReject}
              onSendMessage={sendCsrMessage}
            />
          </div>

          {/* Knowledge + Models — pinned at bottom */}
          <div className="border-t border-gray-800 max-h-[35%] overflow-y-auto">
            <KnowledgePanel rules={knowledgeRules} mode={mode} />
            <MentalModelsPanel
              models={mentalModels}
              isRefreshing={isRefreshingModels}
            />
          </div>
        </div>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}

export default App;
