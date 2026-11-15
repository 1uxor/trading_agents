import { useEffect, useRef, useState, useCallback } from 'react';
import type { CommentaryEvent } from '../types';

export function useWebSocket() {
  const [events, setEvents] = useState<CommentaryEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Keep-alive ping every 30s
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 30000);
      ws.addEventListener('close', () => clearInterval(ping));
    };

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as CommentaryEvent;
        setEvents((prev) => [...prev.slice(-499), data]);
      } catch { /* ignore non-JSON */ }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}
