import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { AgentSummary, CommentaryEvent } from '../types';

interface Props {
  symbol: string;
  agents: AgentSummary[];
  events: CommentaryEvent[];
}

export function Chart({ symbol, agents, events }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;
      setLoading(true);

      // Dynamic import of lightweight-charts
      const { createChart, ColorType } = await import('lightweight-charts');

      if (cancelled || !containerRef.current) return;

      // Destroy previous
      if (chartRef.current) {
        chartRef.current.remove();
      }

      const chart = createChart(containerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: '#0a0a0f' },
          textColor: '#6b7280',
          fontFamily: 'JetBrains Mono',
        },
        grid: {
          vertLines: { color: '#1f2937' },
          horzLines: { color: '#1f2937' },
        },
        width: containerRef.current.clientWidth,
        height: 400,
        crosshair: {
          mode: 0,
        },
        timeScale: {
          borderColor: '#1f2937',
          timeVisible: true,
        },
        rightPriceScale: {
          borderColor: '#1f2937',
        },
      });

      chartRef.current = chart;

      const series = chart.addCandlestickSeries({
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderDownColor: '#ef4444',
        borderUpColor: '#22c55e',
        wickDownColor: '#ef4444',
        wickUpColor: '#22c55e',
      });

      seriesRef.current = series;

      // Fetch data
      try {
        const { data } = await api.getOHLCV(symbol, 'H1', 200);
        if (cancelled) return;

        const candles = data.map((bar: any) => ({
          time: bar.time as number,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        }));

        series.setData(candles);
        chart.timeScale().fitContent();
      } catch (e) {
        console.error('Chart data error:', e);
      }

      // Resize observer
      const ro = new ResizeObserver(() => {
        if (containerRef.current) {
          chart.applyOptions({ width: containerRef.current.clientWidth });
        }
      });
      ro.observe(containerRef.current);

      setLoading(false);

      return () => {
        ro.disconnect();
        chart.remove();
      };
    }

    init();
    return () => { cancelled = true; };
  }, [symbol]);

  // Add trade markers from events
  useEffect(() => {
    if (!seriesRef.current) return;

    const tradeEvents = events.filter(
      (e) =>
        e.event === 'result' &&
        e.data?.symbol === symbol &&
        e.data?.fill_price &&
        e.data?.ticket
    );

    const markers = tradeEvents.map((evt) => ({
      time: Math.floor(new Date(evt.timestamp).getTime() / 1000) as any,
      position: (evt.data?.direction === 'BUY' ? 'belowBar' : 'aboveBar') as any,
      color: evt.color,
      shape: (evt.data?.direction === 'BUY' ? 'arrowUp' : 'arrowDown') as any,
      text: `${evt.agent_name} ${evt.data?.direction}`,
    }));

    if (markers.length > 0) {
      try {
        seriesRef.current.setMarkers(markers);
      } catch { /* ignore marker errors */ }
    }
  }, [events, symbol]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-400 font-mono">{symbol} H1</h3>
        {loading && <span className="text-xs text-gray-600">Loading...</span>}
      </div>
      <div ref={containerRef} className="w-full" style={{ minHeight: 400 }} />
    </div>
  );
}
