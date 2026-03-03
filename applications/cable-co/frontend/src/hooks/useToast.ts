import { useState, useCallback, useRef } from 'react';

export interface Toast {
  id: number;
  message: string;
  type: 'error' | 'success' | 'info';
}

let nextId = 0;

export function useToast(autoDismissMs = 5000) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    const timer = timersRef.current.get(id);
    if (timer) clearTimeout(timer);
    timersRef.current.delete(id);
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((message: string, type: Toast['type'] = 'error') => {
    const id = nextId++;
    setToasts(prev => [...prev, { id, message, type }]);
    const timer = setTimeout(() => dismiss(id), autoDismissMs);
    timersRef.current.set(id, timer);
    return id;
  }, [autoDismissMs, dismiss]);

  const showError = useCallback((message: string) => addToast(message, 'error'), [addToast]);
  const showSuccess = useCallback((message: string) => addToast(message, 'success'), [addToast]);
  const showInfo = useCallback((message: string) => addToast(message, 'info'), [addToast]);

  return { toasts, showError, showSuccess, showInfo, dismiss };
}
