import { useEffect, useRef, useCallback, useState } from 'react';
import { useGameStore } from '../stores/gameStore';
import type { ServerEvent } from '../types';

const CLIENT_ID = `client-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const { connected, setConnected, handleEvent, difficulty } = useGameStore();

  const connect = useCallback(async () => {
    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    setIsConnecting(true);

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Fetch the actual difficulty from the backend before connecting
    let actualDifficulty = difficulty;
    try {
      const res = await fetch('/api/difficulty?app=demo');
      const data = await res.json();
      if (data.difficulty) {
        actualDifficulty = data.difficulty;
      }
    } catch (e) {
      console.warn('Failed to fetch difficulty, using store default:', difficulty);
    }

    // Connect directly to backend WebSocket (bypass Vite proxy)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // In dev, connect directly to backend; in prod, use same host
    const port = window.location.port;
    const isDev = port === '5173' || port === '5174' || port.startsWith('517');
    const wsHost = isDev ? `${window.location.hostname}:8000` : window.location.host;
    // Pass app=demo and difficulty to identify this as the demo frontend
    const wsUrl = `${protocol}//${wsHost}/ws/${CLIENT_ID}?app=demo&difficulty=${actualDifficulty}`;
    console.log('Connecting to WebSocket:', wsUrl, 'difficulty:', actualDifficulty);

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected successfully to:', wsUrl);
      setIsConnecting(false);
    };

    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      setConnected(false);
      setIsConnecting(false);
      wsRef.current = null;

      // Reconnect after 3 seconds (longer delay to avoid spam)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = window.setTimeout(() => {
        console.log('Attempting reconnect...');
        connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      console.log('WebSocket raw message:', event.data);
      try {
        const data = JSON.parse(event.data) as ServerEvent;
        console.log('WebSocket parsed event:', data.type, data);
        handleEvent(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    wsRef.current = ws;
  }, [setConnected, handleEvent, difficulty]);

  const send = useCallback((type: string, payload?: unknown) => {
    const doSend = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        console.log('WebSocket sending:', type);
        wsRef.current.send(JSON.stringify({ type, payload }));
        return true;
      }
      return false;
    };

    if (!doSend()) {
      console.log('WebSocket not ready, retrying send in 500ms:', type);
      // Retry after a short delay to allow reconnection
      setTimeout(() => {
        if (!doSend()) {
          console.error('WebSocket still not connected after retry, state:', wsRef.current?.readyState);
        }
      }, 500);
    }
  }, []);

  interface HindsightSettings {
    inject: boolean;
    reflect: boolean;
    store: boolean;
    query?: string;  // Custom memory query
  }

  const startDelivery = useCallback((
    recipientName: string,
    includeBusiness: boolean,
    maxSteps?: number | null,
    model?: string,
    hindsight?: HindsightSettings
  ) => {
    send('start_delivery', {
      recipientName,
      includeBusiness,
      maxSteps: maxSteps ?? undefined,
      model: model ?? undefined,
      hindsight: hindsight ?? undefined
    });
  }, [send]);

  const cancelDelivery = useCallback(() => {
    send('cancel_delivery');
  }, [send]);

  const resetMemory = useCallback(() => {
    send('reset_memory');
  }, [send]);

  const sendSetDifficulty = useCallback((newDifficulty: string) => {
    send('set_difficulty', { difficulty: newDifficulty });
  }, [send]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []); // Empty deps - only run once on mount

  // Send difficulty change to backend when difficulty changes
  const prevDifficultyRef = useRef(difficulty);
  useEffect(() => {
    if (prevDifficultyRef.current !== difficulty && wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('Difficulty changed, sending set_difficulty to backend:', difficulty);
      sendSetDifficulty(difficulty);
    }
    prevDifficultyRef.current = difficulty;
  }, [difficulty, sendSetDifficulty]);

  return {
    connected,
    isConnecting,
    send,
    startDelivery,
    cancelDelivery,
    resetMemory,
    sendSetDifficulty,
  };
}
