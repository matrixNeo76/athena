/**
 * useWebSocket — real-time pipeline progress hook for ATHENA.
 *
 * Connects to the backend WebSocket endpoint for a given job and exposes
 * live progress messages. Falls back to polling if the browser or network
 * does not support WebSocket connections.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { buildWsUrl, getStatus } from '../lib/api';
import type { WsProgressMessage, StatusResponse } from '../types/athena';

export type WsStatus = 'connecting' | 'open' | 'closed' | 'error' | 'polling';

interface UseWebSocketOptions {
  /** Job ID to subscribe to. Pass null/undefined to skip connection. */
  jobId: string | null | undefined;
  /** Called each time a new progress message arrives. */
  onMessage?: (msg: WsProgressMessage) => void;
  /** Called when the connection opens. */
  onOpen?: () => void;
  /** Called when the connection closes. */
  onClose?: () => void;
  /** Polling interval in ms (used as fallback). Default: 3000 */
  pollIntervalMs?: number;
  /** Max reconnect attempts before switching to polling. Default: 3 */
  maxReconnects?: number;
}

export function useWebSocket({
  jobId,
  onMessage,
  onOpen,
  onClose,
  pollIntervalMs = 3000,
  maxReconnects = 3,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<WsStatus>('closed');
  const [lastMessage, setLastMessage] = useState<WsProgressMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectsRef = useRef(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // ── Polling fallback ────────────────────────
  const startPolling = useCallback(() => {
    if (!jobId || pollRef.current) return;
    setStatus('polling');

    pollRef.current = setInterval(async () => {
      if (!mountedRef.current) return;
      try {
        const data: StatusResponse = await getStatus(jobId);
        const msg: WsProgressMessage = {
          type: 'progress',
          job_id: jobId,
          stage: data.stage as WsProgressMessage['stage'],
          progress: data.progress ?? 0,
          message: data.message ?? '',
          timestamp: new Date().toISOString(),
        };
        setLastMessage(msg);
        onMessage?.(msg);

        // Stop polling when terminal state reached
        if (data.stage === 'DONE' || data.stage === 'ERROR') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setStatus('closed');
        }
      } catch {
        // Polling errors are non-fatal; just keep trying
      }
    }, pollIntervalMs);
  }, [jobId, onMessage, pollIntervalMs]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // ── WebSocket connection ───────────────────
  const connect = useCallback(() => {
    if (!jobId || typeof window === 'undefined') return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = buildWsUrl(jobId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setStatus('connecting');

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectsRef.current = 0;
      setStatus('open');
      onOpen?.();
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const msg: WsProgressMessage = JSON.parse(event.data);
        setLastMessage(msg);
        onMessage?.(msg);
      } catch {
        // Malformed frame — ignore
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setStatus('error');
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      onClose?.();

      // Auto-reconnect or fall back to polling
      if (reconnectsRef.current < maxReconnects) {
        reconnectsRef.current++;
        const delay = Math.min(1000 * 2 ** reconnectsRef.current, 8000);
        setTimeout(connect, delay);
      } else {
        setStatus('polling');
        startPolling();
      }
    };
  }, [jobId, onMessage, onOpen, onClose, maxReconnects, startPolling]);

  // ── Lifecycle ──────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    if (jobId) connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      stopPolling();
    };
  }, [jobId]); // Re-run only when jobId changes

  return { status, lastMessage };
}
