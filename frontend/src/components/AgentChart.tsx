import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { CommentaryEvent, IndicatorSeries } from '../types';

interface Props {
  symbol: string;
  timeframe: string;
  agentId: string;
  agentColor: string;
  agentName: string;
  events: CommentaryEvent[];
  indicators: IndicatorSeries[];
}

export function AgentChart({ symbol, timeframe, agentId, agentColor, agentName, events, indicators }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const indicatorSeriesRef = useRef<any[]>([]);
  const [loading, setLoading] = useState(false);

  // Initialize chart and load candle data
  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;
      setLoading(true);

      const { createChart, ColorType } = await import('lightweight-charts');

      if (cancelled || !containerRef.current) return;

      // Destroy previous
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        indicatorSeriesRef.current = [];
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
        height: 420,
        crosshair: { mode: 0 },
        timeScale: { borderColor: '#1f2937', timeVisible: true },
        rightPriceScale: { borderColor: '#1f2937' },
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
          const { data } = await api.getOHLCV(symbol, timeframe, 200);
          if (cancelled) return;

          const candles = data.map((bar: any) => ({
            time: bar.time as any,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          }));

          series.setData(candles);
          if (fitContent) chart.timeScale().fitContent();
        } catch (e) {
          console.error('AgentChart data error:', e);
        }
      }

      await fetchCandles(true);

      // Auto-refresh every 10 seconds
      const refreshInterval = setInterval(() => fetchCandles(false), 10_000);

      // Resize observer
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
  }, [symbol, timeframe]);

  // Draw indicator overlays
  useEffect(() => {
    if (!chartRef.current || !indicators.length) return;

    // Clean up previous indicator series
    indicatorSeriesRef.current.forEach((s) => {
      try { chartRef.current.removeSeries(s); } catch { /* ignore */ }
    });
    indicatorSeriesRef.current = [];

    let hasRsi = false;

    for (const ind of indicators) {
      if (ind.type === 'line' && ind.data.length > 0) {
        const lineSeries = chartRef.current.addLineSeries({
          color: ind.color,
          lineWidth: 2,
          title: ind.label,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        lineSeries.setData(ind.data);
        indicatorSeriesRef.current.push(lineSeries);

      } else if (ind.type === 'rsi' && ind.data.length > 0) {
        hasRsi = true;
        // RSI on separate left price scale
        const rsiSeries = chartRef.current.addLineSeries({
          color: ind.color,
          lineWidth: 2,
          title: ind.label,
          priceScaleId: 'rsi',
          priceLineVisible: false,
          lastValueVisible: true,
        });
        rsiSeries.setData(ind.data);
        indicatorSeriesRef.current.push(rsiSeries);

        // Add oversold/overbought reference lines
        if (ind.oversold != null) {
          rsiSeries.createPriceLine({
            price: ind.oversold,
            color: '#4CAF5060',
            lineWidth: 1,
            lineStyle: 2,
            title: `${ind.oversold}`,
          });
        }
        if (ind.overbought != null) {
          rsiSeries.createPriceLine({
            price: ind.overbought,
            color: '#F4433660',
            lineWidth: 1,
            lineStyle: 2,
            title: `${ind.overbought}`,
          });
        }
        // Mid line at 50
        rsiSeries.createPriceLine({
          price: 50,
          color: '#6b728040',
          lineWidth: 1,
          lineStyle: 2,
          title: '50',
        });
      }
    }

    // Configure left price scale for RSI if present
    if (hasRsi) {
      chartRef.current.applyOptions({
        leftPriceScale: { visible: true, borderColor: '#1f2937' },
      });
    }
  }, [indicators]);

  // Add trade markers from this agent's events
  useEffect(() => {
    if (!seriesRef.current) return;

    const tradeEvents = events.filter(
      (e) =>
        e.agent_id === agentId &&
        e.event === 'result' &&
        e.data?.symbol === symbol &&
        e.data?.fill_price &&
        e.data?.ticket
    );

    const markers = tradeEvents.map((evt) => ({
      time: Math.floor(new Date(evt.timestamp).getTime() / 1000) as any,
      position: (evt.data?.direction === 'BUY' ? 'belowBar' : 'aboveBar') as any,
      color: agentColor,
      shape: (evt.data?.direction === 'BUY' ? 'arrowUp' : 'arrowDown') as any,
      text: `${agentName} ${evt.data?.direction}`,
    }));

    if (markers.length > 0) {
      try { seriesRef.current.setMarkers(markers); } catch { /* ignore */ }
    }
  }, [events, symbol, agentId]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-400 font-mono">{symbol} {timeframe}</h3>
          {/* Indicator legend */}
          <div className="flex items-center gap-2">
            {indicators.filter(i => i.type !== 'forecast_placeholder').map((ind, idx) => (
              <span key={idx} className="flex items-center gap-1 text-xs text-gray-500">
                <span className="w-3 h-0.5 inline-block rounded" style={{ backgroundColor: ind.color }} />
                {ind.label}
              </span>
            ))}
          </div>
        </div>
        {loading && <span className="text-xs text-gray-600">Loading...</span>}
      </div>
      <div ref={containerRef} className="w-full" style={{ minHeight: 420 }} />
    </div>
  );
}
