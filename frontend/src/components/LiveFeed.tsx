import { useEffect, useRef } from 'react';
import type { CommentaryEvent } from '../types';

interface Props {
  events: CommentaryEvent[];
  maxItems?: number;
}

export function LiveFeed({ events, maxItems = 100 }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  const display = events.slice(-maxItems);

  const eventIcons: Record<string, string> = {
    thinking: '\u{1F914}',
    signal: '\u{1F4CA}',
    executing: '\u{26A1}',
    result: '\u{2705}',
    explanation: '\u{1F4AC}',
    error: '\u{274C}',
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl">
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-400">Live Feed</h3>
        <span className="text-xs text-gray-600">{events.length} events</span>
      </div>
      <div className="h-64 overflow-y-auto px-4 py-2 space-y-1 font-mono text-sm">
        {display.length === 0 && (
          <p className="text-gray-600 text-center py-8">No events yet. Start an agent to see live commentary.</p>
        )}
        {display.map((evt, i) => {
          const time = new Date(evt.timestamp).toLocaleTimeString();
          return (
            <div key={i} className="flex items-start gap-2 py-0.5 hover:bg-gray-800/50 rounded px-1">
              <span
                className="w-2 h-2 mt-1.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: evt.color }}
              />
              <span className="text-gray-600 flex-shrink-0">{time}</span>
              <span className="flex-shrink-0">{eventIcons[evt.event] || ''}</span>
              <span className="text-gray-500 flex-shrink-0" style={{ color: evt.color }}>
                {evt.agent_name}:
              </span>
              <span className="text-gray-300">{evt.message}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
