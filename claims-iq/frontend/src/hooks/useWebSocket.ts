import { useRef, useCallback, useEffect } from 'react';
import { useClaimsStore } from '../stores/claimsStore.ts';
import type { AgentMode, Claim, AgentAction, AgentMistake, MemoryInjection, ClaimResult, ServerEvent } from '../types.ts';

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
    const wsHost = isDev ? `${window.location.hostname}:8001` : window.location.host;
    const ws = new WebSocket(`${protocol}//${wsHost}/ws/${CLIENT_ID}`);

    ws.onopen = () => {
      console.log('[WS] Connected');
    };

    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data) as ServerEvent;
        const store = useClaimsStore.getState();
        const p = evt.payload ?? {};

        switch (evt.type) {
          case 'CONNECTED':
            store.setConnected(true, p.bankId as string, p.mode as AgentMode);
            break;
          case 'CLAIM_RECEIVED':
            store.setClaim(p as unknown as Claim);
            break;
          case 'AGENT_THINKING':
            store.setThinking(true);
            break;
          case 'AGENT_ACTION':
            store.addAction(p as unknown as AgentAction);
            break;
          case 'CLAIM_STAGE_UPDATE':
            store.setStage(p.stage as 'classified' | 'verified' | 'routed' | 'resolved');
            break;
          case 'MEMORY_INJECTED':
            store.setMemoryInjection(p as unknown as MemoryInjection);
            break;
          case 'MEMORY_STORING':
            store.setStoringMemory(true);
            break;
          case 'MEMORY_STORED':
            store.setStoringMemory(false);
            break;
          case 'MODELS_REFRESHING':
            store.setRefreshingModels(true);
            break;
          case 'MODELS_REFRESHED':
            store.setRefreshingModels(false);
            break;
          case 'CLAIM_RESOLVED': {
            const claim = store.currentClaim;
            const result: ClaimResult = {
              claimId: claim?.claimId ?? '',
              category: claim?.category ?? '',
              decision: p.decision as string,
              correct: p.correct as boolean,
              steps: p.steps as number,
              optimalSteps: p.optimalSteps as number,
              reworkCount: (p.reworkCount as number) ?? 0,
              mistakes: (p.mistakes as AgentMistake[]) ?? [],
              expectedWorkflow: (p.expectedWorkflow as string[]) ?? [],
              actualWorkflow: (p.actualWorkflow as string[]) ?? [],
            };
            store.resolveClaim(result);
            break;
          }
          case 'ERROR':
            onErrorRef.current?.(p.message as string);
            break;
        }
      } catch (err) {
        console.error('[WS] Parse error:', err);
      }
    };

    ws.onclose = () => {
      useClaimsStore.getState().setConnected(false);
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

  const processClaim = useCallback((scenarioId?: string, maxSteps?: number) => {
    send('process_claim', { scenarioId, maxSteps: maxSteps ?? 20 });
  }, [send]);

  const cancelClaim = useCallback(() => {
    send('cancel');
  }, [send]);

  const resetMemory = useCallback(() => {
    send('reset_memory');
  }, [send]);

  const setMode = useCallback((mode: AgentMode) => {
    useClaimsStore.getState().setMode(mode);
    send('set_mode', { mode });
  }, [send]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []); // Only run once on mount

  return { processClaim, cancelClaim, resetMemory, setMode, connected: useClaimsStore.getState().connected };
}
