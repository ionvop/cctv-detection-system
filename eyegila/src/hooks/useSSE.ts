import { useEffect, useRef, useState } from 'react';

export type SSEStatus = 'connecting' | 'connected' | 'disconnected';

const MAX_RETRY_MS = 30_000;

export function useSSE<T>(url: string, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<SSEStatus>('disconnected');

  const esRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelayRef = useRef(1_000);
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  useEffect(() => {
    if (!enabled) {
      setStatus('disconnected');
      return;
    }

    function connect() {
      if (!enabledRef.current) return;

      setStatus('connecting');
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        setStatus('connected');
        retryDelayRef.current = 1_000; // reset backoff on success
      };

      es.onmessage = (ev: MessageEvent) => {
        try {
          setData(JSON.parse(ev.data) as T);
        } catch {
          // malformed JSON -ignore
        }
      };

      es.onerror = () => {
        setStatus('disconnected');
        es.close();
        esRef.current = null;

        const delay = retryDelayRef.current;
        retryDelayRef.current = Math.min(delay * 2, MAX_RETRY_MS);
        retryTimerRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      esRef.current?.close();
      esRef.current = null;
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, [url, enabled]);

  return { data, status };
}
