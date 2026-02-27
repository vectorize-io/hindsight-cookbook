import { useRef, useCallback, useEffect } from 'react';
import { useSessionStore } from '../stores/sessionStore.ts';
import type { AgentMode, CustomerScenario, AgentAction, PendingSuggestion, MemoryRecall, KnowledgeRule, ScenarioResult, ServerEvent } from '../types.ts';

const CLIENT_ID = `client-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export function useWebSocket(onError?: (msg: string) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const port = window.location.port;
    const isDev = port === '5173' || port === '5174' || port.startsWith('517');
    const wsHost = isDev ? `${window.location.hostname}:8002` : window.location.host;
    const ws = new WebSocket(`${protocol}//${wsHost}/ws/${CLIENT_ID}`);

    ws.onopen = () => {
      console.log('[WS] Connected');
    };

    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data) as ServerEvent;
        const store = useSessionStore.getState();
        const p = evt.payload ?? {};

        switch (evt.type) {
          case 'CONNECTED':
            store.setConnected(true, p.bankId as string, p.mode as AgentMode, p.totalScenarios as number);
            break;
          case 'SCENARIO_LOADED':
            store.setScenario(p as unknown as CustomerScenario);
            break;
          case 'AGENT_THINKING':
            store.setThinking(true);
            break;
          case 'AGENT_LOOKUP':
            store.addAction(p as unknown as AgentAction);
            break;
          case 'AGENT_SUGGESTION':
            // Agent proposed an action — show it pending CSR approval
            store.setPendingSuggestion(p as unknown as PendingSuggestion);
            break;
          case 'CSR_APPROVED':
            store.resolveSuggestion(
              p.suggestionId as string,
              true,
              '',
              p.result as string,
            );
            break;
          case 'CSR_REJECTED':
            store.resolveSuggestion(
              p.suggestionId as string,
              false,
              p.feedback as string,
              '',
            );
            break;
          case 'MEMORY_RECALLED':
            store.setMemoryRecall(p as unknown as MemoryRecall);
            break;
          case 'MEMORY_STORING':
            store.setStoringMemory(true);
            break;
          case 'MEMORY_STORED':
            store.setStoringMemory(false);
            break;
          case 'KNOWLEDGE_UPDATED':
            store.addKnowledgeRule(p as unknown as KnowledgeRule);
            break;
          case 'MODELS_REFRESHING':
            store.setRefreshingModels(true);
            break;
          case 'MODELS_REFRESHED':
            store.setRefreshingModels(false);
            break;
          case 'RESPONSE_SENT':
            store.addSentResponse(p.message as string);
            break;
          case 'CUSTOMER_REPLY':
            store.addCustomerReply(p.message as string);
            break;
          case 'SCENARIO_RESOLVED_PREVIEW':
            // Resolve preview (terminal tool) — add as action
            store.addAction(p as unknown as AgentAction);
            break;
          case 'SCENARIO_RESOLVED':
            store.resolveScenario(p as unknown as ScenarioResult);
            break;
          case 'ERROR':
            onErrorRef.current?.(p.message as string);
            break;
        }
      } catch (err) {
        console.error('[WS] Parse error:', err);
      }
    };

    ws.onclose = () => {
      useSessionStore.getState().setConnected(false);
      console.log('[WS] Disconnected, reconnecting in 3s...');
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error('[WS] Error:', err);
    };

    wsRef.current = ws;
  }, []);

  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  const processNext = useCallback(() => {
    send('process_next');
  }, [send]);

  const cancel = useCallback(() => {
    send('cancel');
  }, [send]);

  const resetMemory = useCallback(() => {
    useSessionStore.getState().resetAll();
    send('reset_memory');
  }, [send]);

  const setMode = useCallback((mode: AgentMode) => {
    useSessionStore.getState().setMode(mode);
    send('set_mode', { mode });
  }, [send]);

  /** CSR approves or rejects a pending suggestion */
  const csrRespond = useCallback((suggestionId: string, approved: boolean, feedback: string) => {
    send('csr_respond', { suggestionId, approved, feedback });
  }, [send]);

  /** CSR sends freeform feedback to the copilot */
  const sendCsrMessage = useCallback((message: string) => {
    useSessionStore.getState().addCsrMessage(message);
    send('csr_message', { message });
  }, [send]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return { processNext, cancel, resetMemory, setMode, csrRespond, sendCsrMessage };
}
