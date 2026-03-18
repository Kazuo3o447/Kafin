"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, Time, CandlestickSeries, LineSeries, SeriesMarker } from "lightweight-charts";
import { api } from "@/lib/api";

type InteractiveChartProps = {
  ticker: string;
};

export default function InteractiveChart({ ticker }: InteractiveChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 1. Chart initialisieren
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#374151" }, // var(--border) like
        horzLines: { color: "#374151" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });
    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e", // var(--accent-green)
      downColor: "#ef4444", // var(--accent-red)
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const sma50Series = chart.addSeries(LineSeries, {
      color: "#3b82f6", // blue
      lineWidth: 2,
      title: "SMA 50",
    });

    const sma200Series = chart.addSeries(LineSeries, {
      color: "#eab308", // yellow/amber
      lineWidth: 2,
      title: "SMA 200",
    });

    // 2. Daten laden
    const fetchData = async () => {
      setLoading(true);
      try {
        const [ohlcv, overlays] = await Promise.all([
          api.getOhlcv(ticker, "1y", "1d"), // 1y damit SMA200 berechnet werden kann (Backend macht calculation serverseitig, aber returns only valid periods)
          api.getChartOverlays(ticker),
        ]);

        if (ohlcv.candles) {
          candlestickSeries.setData(ohlcv.candles);
        }
        if (ohlcv.sma_50) {
          sma50Series.setData(ohlcv.sma_50);
        }
        if (ohlcv.sma_200) {
          sma200Series.setData(ohlcv.sma_200);
        }

        // 3. Overlays / Markers verarbeiten
        const markers: SeriesMarker<Time>[] = [];

        // Earnings
        if (overlays.earnings_events) {
          overlays.earnings_events.forEach((ev: any) => {
            markers.push({
              time: ev.time as Time,
              position: "aboveBar",
              color: "#a855f7", // purple
              shape: "circle",
              text: ev.label || "E",
            });
          });
        }

        // Torpedos
        if (overlays.torpedo_alerts) {
          overlays.torpedo_alerts.forEach((ev: any) => {
            markers.push({
              time: ev.time as Time,
              position: "aboveBar",
              color: "#ef4444", // red
              shape: "arrowDown",
              text: "⚠️ " + ev.event_text,
            });
          });
        }

        // Insider
        if (overlays.insider_transactions) {
          overlays.insider_transactions.forEach((ev: any) => {
            if (ev.direction === "buy" && ev.amount_usd > 100000) {
              markers.push({
                time: ev.time as Time,
                position: "belowBar",
                color: "#22c55e",
                shape: "arrowUp",
                text: `Insider Buy ($${(ev.amount_usd / 1000).toFixed(0)}k)`,
              });
            } else if (ev.direction === "sell" && ev.amount_usd > 500000) {
              // Nur große Sells anzeigen
              markers.push({
                time: ev.time as Time,
                position: "aboveBar",
                color: "#f59e0b",
                shape: "arrowDown",
                text: `Insider Sell ($${(ev.amount_usd / 1000).toFixed(0)}k)`,
              });
            }
          });
        }

        // Narrative Shifts
        if (overlays.narrative_shifts) {
            overlays.narrative_shifts.forEach((ev: any) => {
                markers.push({
                    time: ev.time as Time,
                    position: "belowBar",
                    color: "#3b82f6", // blue
                    shape: "square",
                    text: `Shift: ${ev.shift_type}`
                });
            });
        }

        // Sort markers by time (required by lightweight-charts)
        markers.sort((a, b) => (a.time as string).localeCompare(b.time as string));
        
        // Cast to any to avoid TS error: Property 'setMarkers' does not exist...
        (candlestickSeries as any).setMarkers(markers);
        
        // Fit Content
        chart.timeScale().fitContent();

      } catch (err) {
        console.error("Chart data fetch error", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    // Resize Handler
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if(chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [ticker]);

  return (
    <div className="relative h-[400px] w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-2">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[var(--bg-tertiary)]/80 z-10">
          <p className="text-sm text-[var(--text-muted)]">Lade Chart-Daten...</p>
        </div>
      )}
      <div ref={chartContainerRef} className="h-full w-full" />
    </div>
  );
}

