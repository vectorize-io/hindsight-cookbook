import { useEffect, useRef, useCallback, useState } from 'react';
import { useGameStore } from '../stores/gameStore';
import type { ServerEvent } from '../types';

const CLIENT_ID = `client-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const { connected, setConnected, handleEvent } = useGameStore();

  const connect = useCallback(() => {
    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    setIsConnecting(true);

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Connect directly to backend WebSocket (bypass Vite proxy)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // In dev, connect directly to backend; in prod, use same host
    const port = window.location.port;
    const isDev = port === '5173' || port === '5174' || port.startsWith('517');
    const wsHost = isDev ? `${window.location.hostname}:8001` : window.location.host;
    const wsUrl = `${protocol}//${wsHost}/ws/${CLIENT_ID}`;
    console.log('Connecting to WebSocket:', wsUrl);

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
  }, [setConnected, handleEvent]);

  const send = useCallback((type: string, payload?: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    } else {
      console.error('WebSocket not connected, state:', wsRef.current?.readyState);
    }
  }, []);

  interface HindsightSettings {
    inject: boolean;
    reflect: boolean;
    store: boolean;
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

  return {
    connected,
    isConnecting,
    send,
    startDelivery,
    cancelDelivery,
    resetMemory,
  };
}
