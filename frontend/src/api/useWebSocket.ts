import { useEffect, useRef, useState, useCallback } from 'react';
import type { CommentaryEvent } from '../types';

export function useWebSocket() {
  const [events, setEvents] = useState<CommentaryEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const seenIds = useRef(new Set<string>());

  const connect = useCallback(() => {
    // Prevent duplicate connections (React StrictMode double-mount)
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      return;
    }

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
        // Deduplicate by timestamp + agent_id + message
        const eventKey = `${data.timestamp}:${data.agent_id}:${data.event}:${data.message}`;
        if (seenIds.current.has(eventKey)) return;
        seenIds.current.add(eventKey);
        // Keep dedup set bounded
        if (seenIds.current.size > 1000) {
          const entries = Array.from(seenIds.current);
          seenIds.current = new Set(entries.slice(-500));
        }
        setEvents((prev) => [...prev.slice(-499), data]);
      } catch { /* ignore non-JSON */ }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    seenIds.current.clear();
  }, []);

  return { events, connected, clearEvents };
}
