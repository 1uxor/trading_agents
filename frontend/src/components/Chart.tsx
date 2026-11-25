import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { AgentSummary, CommentaryEvent } from '../types';

interface Props {
  symbol: string;
  agents: AgentSummary[];
  events: CommentaryEvent[];
}

interface SessionDef {
  name: string;
  startHour: number; // UTC
  endHour: number;   // UTC
  color: string;
  bgColor: string;
}

const SESSIONS: SessionDef[] = [
  { name: 'Sydney',  startHour: 21, endHour: 6,  color: '#a78bfa', bgColor: 'rgba(167,139,250,0.07)' },
  { name: 'Tokyo',   startHour: 0,  endHour: 9,  color: '#60a5fa', bgColor: 'rgba(96,165,250,0.07)' },
  { name: 'London',  startHour: 7,  endHour: 16, color: '#34d399', bgColor: 'rgba(52,211,153,0.07)' },
  { name: 'New York',startHour: 12, endHour: 21, color: '#fb923c', bgColor: 'rgba(251,146,60,0.07)' },
];

function isInSession(hourUTC: number, session: SessionDef): boolean {
  if (session.startHour < session.endHour) {
    return hourUTC >= session.startHour && hourUTC < session.endHour;
  }
  // Wraps midnight (e.g. Sydney 21-6)
  return hourUTC >= session.startHour || hourUTC < session.endHour;
}

export function Chart({ symbol, agents, events }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const sessionSeriesRef = useRef<Map<string, any>>(new Map());
  const markersRef = useRef<any[]>([]);
  const candlesRef = useRef<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showSessions, setShowSessions] = useState<Record<string, boolean>>({
    Sydney: false,
    Tokyo: false,
    London: true,
    'New York': true,
  });

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;
      setLoading(true);

      const { createChart, ColorType } = await import('lightweight-charts');

      if (cancelled || !containerRef.current) return;

      if (chartRef.current) {
        chartRef.current.remove();
      }
      sessionSeriesRef.current.clear();

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

      async function fetchCandles(fitContent = false) {
        try {
          const { data } = await api.getOHLCV(symbol, 'H1', 200);
          if (cancelled) return;

          const candles = data.map((bar: any) => ({
            time: bar.time as any,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          }));

          candlesRef.current = candles;
          series.setData(candles);
          if (fitContent) chart.timeScale().fitContent();
        } catch (e) {
          console.error('Chart data error:', e);
        }
      }

      await fetchCandles(true);

      const refreshInterval = setInterval(() => fetchCandles(false), 10_000);

      const ro = new ResizeObserver(() => {
        if (containerRef.current) {
          chart.applyOptions({ width: containerRef.current.clientWidth });
        }
      });
      ro.observe(containerRef.current);

      setLoading(false);

      return () => {
        clearInterval(refreshInterval);
        ro.disconnect();
        chart.remove();
      };
    }

    init();
    return () => { cancelled = true; };
  }, [symbol]);

  // Manage session highlight series
  useEffect(() => {
    const chart = chartRef.current;
    const candles = candlesRef.current;
    if (!chart || candles.length === 0) return;

    // Remove old session series
    for (const [key, s] of sessionSeriesRef.current.entries()) {
      try { chart.removeSeries(s); } catch { /* ignore */ }
    }
    sessionSeriesRef.current.clear();

    // Create series for each enabled session
    for (const session of SESSIONS) {
      if (!showSessions[session.name]) continue;

      // Build data: for each candle, if it's in the session, draw a line at the candle's high
      // We use a histogram series at the bottom with a fixed value to create color bands
      const high = Math.max(...candles.map((c: any) => c.high));
      const low = Math.min(...candles.map((c: any) => c.low));
      const range = high - low;

      // Use a line series with area fill to create session bands
      const sessionSeries = chart.addLineSeries({
        color: 'transparent',
        lineWidth: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });

      // For area-like appearance, we set lineType step and use the area
      // Actually, let's use addHistogramSeries which supports color per bar
      try { chart.removeSeries(sessionSeries); } catch { /* */ }

      // Best approach: use a separate area series per session
      const areaSeries = chart.addAreaSeries({
        topColor: session.bgColor,
        bottomColor: 'transparent',
        lineColor: 'transparent',
        lineWidth: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });

      const areaData = candles.map((c: any) => {
        const ts = c.time;
        const hourUTC = typeof ts === 'number'
          ? new Date(ts * 1000).getUTCHours()
          : new Date(ts).getUTCHours();
        return {
          time: c.time,
          value: isInSession(hourUTC, session) ? high + range * 0.02 : low,
        };
      });

      areaSeries.setData(areaData);
      sessionSeriesRef.current.set(session.name, areaSeries);
    }
  }, [showSessions, candlesRef.current.length]);

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

  const toggleSession = (name: string) => {
    setShowSessions((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-400 font-mono">{symbol} H1</h3>
        <div className="flex items-center gap-2">
          {SESSIONS.map((s) => (
            <button
              key={s.name}
              onClick={() => toggleSession(s.name)}
              className={`flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-full border transition-colors ${
                showSessions[s.name]
                  ? 'border-opacity-60 text-white'
                  : 'border-gray-700 text-gray-600 hover:text-gray-400'
              }`}
              style={{
                borderColor: showSessions[s.name] ? s.color : undefined,
                backgroundColor: showSessions[s.name] ? s.bgColor : undefined,
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: s.color, opacity: showSessions[s.name] ? 1 : 0.3 }}
              />
              {s.name}
            </button>
          ))}
          {loading && <span className="text-xs text-gray-600">Loading...</span>}
        </div>
      </div>
      <div ref={containerRef} className="w-full" style={{ minHeight: 400 }} />
    </div>
  );
}
