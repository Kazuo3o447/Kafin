"use client";

import { useState, useEffect, useRef, useCallback, MutableRefObject } from "react";
import {
  createChart,
  CrosshairMode,
  LineStyle,
  IChartApi,
  ISeriesApi,
  IPriceLine,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  Time,
} from "lightweight-charts";
import {
  LineChart,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";

type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type SeriesPoint = { time: string; value: number };

type OhlcvData = {
  ticker: string;
  period: string;
  interval: string;
  candles: Candle[];
  sma_50: SeriesPoint[];
  sma_200: SeriesPoint[];
  error?: string;
};

type OverlayData = {
  earnings_events: {
    time: string;
    timing: string;
    eps_surprise_pct: number | null;
    reaction_1d_pct: number | null;
    recommendation: string;
    label: string;
  }[];
  torpedo_alerts: { time: string; event_text: string; torpedo_score: number }[];
  narrative_shifts: { time: string; shift_type: string; summary: string; sentiment_delta: number }[];
  insider_transactions: { time: string; direction: string; name: string; role: string; amount_usd: number }[];
};

type AiLevels = {
  support_levels: { price: number; strength: string; label: string }[];
  resistance_levels: { price: number; strength: string; label: string }[];
  entry_zone: { low: number; high: number } | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  analysis_text: string;
  bias: string;
  key_risk: string;
  error?: boolean;
};

type TooltipState = { x: number; y: number };

type CandlestickSeriesApi = ISeriesApi<"Candlestick">;

const setMarkersSafe = (series: CandlestickSeriesApi, markers: any[]) => {
  if (!series || typeof (series as any).setMarkers !== "function") return;
  (series as any).setMarkers(markers);
};

function drawAiLevels(
  candleSeries: CandlestickSeriesApi,
  levels: AiLevels,
  priceLinesRef: MutableRefObject<IPriceLine[]>,
  expectedMovePct?: number | null,
  currentPrice?: number | null
) {
  priceLinesRef.current.forEach((line) => candleSeries.removePriceLine(line));
  priceLinesRef.current = [];

  const addLine = (options: Parameters<typeof candleSeries.createPriceLine>[0]) => {
    const line = candleSeries.createPriceLine(options);
    priceLinesRef.current.push(line);
  };

  levels.support_levels?.forEach((level) => {
    addLine({
      price: level.price,
      color: "#22c55e",
      lineWidth: level.strength === "strong" ? 2 : 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: `S: ${level.label}`,
    });
  });

  levels.resistance_levels?.forEach((level) => {
    addLine({
      price: level.price,
      color: "#ef4444",
      lineWidth: level.strength === "strong" ? 2 : 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: `R: ${level.label}`,
    });
  });

  if (levels.stop_loss) {
    addLine({
      price: levels.stop_loss,
      color: "#dc2626",
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      axisLabelVisible: true,
      title: "Stop Loss",
    });
  }

  if (levels.target_1) {
    addLine({
      price: levels.target_1,
      color: "#22c55e",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "T1",
    });
  }

  if (levels.target_2) {
    addLine({
      price: levels.target_2,
      color: "#22c55e",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "T2",
    });
  }

  // Expected Move Lines
  if (expectedMovePct && currentPrice && candleSeries) {
    const moveUsd = currentPrice * (expectedMovePct / 100);
    
    const upperLine = candleSeries.createPriceLine({
      price: currentPrice + moveUsd,
      color: "#22c55e",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: `+${expectedMovePct.toFixed(1)}% EM`,
    });
    priceLinesRef.current.push(upperLine);

    const lowerLine = candleSeries.createPriceLine({
      price: currentPrice - moveUsd,
      color: "#ef4444",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: `-${expectedMovePct.toFixed(1)}% EM`,
    });
    priceLinesRef.current.push(lowerLine);
  }
}

export function ChartAnalysisSection({
  ticker,
  expectedMovePct,
  currentPrice,
}: {
  ticker: string;
  expectedMovePct?: number | null;
  currentPrice?: number | null;
}) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  const [ohlcvData, setOhlcvData] = useState<OhlcvData | null>(null);
  const [overlayData, setOverlayData] = useState<OverlayData | null>(null);
  const [aiLevels, setAiLevels] = useState<AiLevels | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState<"3mo" | "6mo" | "1y" | "2y">("6mo");
  const [loadingOhlcv, setLoadingOhlcv] = useState(true);
  const [loadingAi, setLoadingAi] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [tooltipContent, setTooltipContent] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState<TooltipState>({ x: 0, y: 0 });

  useEffect(() => {
    setLoadingOhlcv(true);
    const period = activeTimeframe;
    const interval = activeTimeframe === "2y" ? "1wk" : "1d";
    api
      .getOhlcv(ticker, period, interval)
      .then((data) => setOhlcvData(data))
      .catch((err) => {
        console.error("OHLCV fetch error", err);
        setOhlcvData(null);
      })
      .finally(() => setLoadingOhlcv(false));
  }, [ticker, activeTimeframe]);

  useEffect(() => {
    api
      .getChartOverlays(ticker)
      .then((data) => setOverlayData(data))
      .catch((err) => {
        console.error("Overlay fetch error", err);
        setOverlayData(null);
      });
  }, [ticker]);

  useEffect(() => {
    if (!chartContainerRef.current || !ohlcvData || ohlcvData.error || !ohlcvData.candles.length) {
      return;
    }

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    priceLinesRef.current = [];

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 420,
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: true },
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    }) as ISeriesApi<"Candlestick">;
    candleSeries.setData(ohlcvData.candles);
    candleSeriesRef.current = candleSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#6b7280",
      priceFormat: { type: "volume" },
    });
    volumeSeries.setData(
      ohlcvData.candles.map((candle) => ({
        time: candle.time,
        value: candle.volume,
        color: candle.close >= candle.open ? "#22c55e44" : "#ef444444",
      }))
    );

    if (ohlcvData.sma_50.length) {
      const sma50 = chart.addSeries(LineSeries, {
        color: "#3b82f6",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
      });
      sma50.setData(ohlcvData.sma_50);
    }

    if (ohlcvData.sma_200.length) {
      const sma200 = chart.addSeries(LineSeries, {
        color: "#a855f7",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
      });
      sma200.setData(ohlcvData.sma_200);
    }

    if (overlayData) {
      const markers: any[] = [];
      overlayData.earnings_events?.forEach((event) => {
        markers.push({
          time: event.time,
          position: "aboveBar",
          color: event.timing === "pre_market" ? "#3b82f6" : "#a855f7",
          shape: "arrowDown",
          text: event.label || "E",
        });
      });
      overlayData.torpedo_alerts?.forEach((event) => {
        markers.push({
          time: event.time,
          position: "belowBar",
          color: "#ef4444",
          shape: "arrowUp",
          text: "⚠",
        });
      });
      overlayData.narrative_shifts?.forEach((event) => {
        markers.push({
          time: event.time,
          position: "aboveBar",
          color: "#f59e0b",
          shape: "circle",
          text: "◆",
        });
      });
      overlayData.insider_transactions?.forEach((event) => {
        markers.push({
          time: event.time,
          position: event.direction === "buy" ? "belowBar" : "aboveBar",
          color: event.direction === "buy" ? "#22c55e" : "#ef4444",
          shape: event.direction === "buy" ? "arrowUp" : "arrowDown",
          text: event.direction === "buy" ? "▲" : "▼",
        });
      });
      markers.sort((a, b) => (a.time > b.time ? 1 : -1));
      setMarkersSafe(candleSeries, markers);
    }

    if (aiLevels) {
      drawAiLevels(candleSeries, aiLevels, priceLinesRef, expectedMovePct, currentPrice);
    }

    let crosshairHandler: ((param: any) => void) | null = null;
    if (overlayData) {
      crosshairHandler = (param) => {
        if (!param?.time || !param.point || !overlayData) {
          setTooltipContent(null);
          return;
        }
        const timeStr = typeof param.time === "string" ? param.time : param.time.toString();
        const point = param.point;

        const findMatch = () => {
          const torpedo = overlayData.torpedo_alerts?.find((e) => e.time === timeStr);
          if (torpedo) {
            return `⚠️ Torpedo: ${torpedo.event_text}`;
          }
          const narrative = overlayData.narrative_shifts?.find((e) => e.time === timeStr);
          if (narrative) {
            return `◆ ${narrative.shift_type}: ${narrative.summary}`;
          }
          const insider = overlayData.insider_transactions?.find((e) => e.time === timeStr);
          if (insider) {
            const dir = insider.direction === "buy" ? "▲ Kauf" : "▼ Verkauf";
            const amount = insider.amount_usd ? ` — $${(insider.amount_usd / 1000).toFixed(0)}k` : "";
            return `${dir}: ${insider.name}${amount}`;
          }
          const earnings = overlayData.earnings_events?.find((e) => e.time === timeStr);
          if (earnings) {
            const surprise =
              earnings.eps_surprise_pct != null
                ? ` EPS ${earnings.eps_surprise_pct > 0 ? "+" : ""}${earnings.eps_surprise_pct.toFixed(1)}%`
                : "";
            const reaction =
              earnings.reaction_1d_pct != null
                ? ` → ${earnings.reaction_1d_pct > 0 ? "+" : ""}${earnings.reaction_1d_pct.toFixed(1)}%`
                : "";
            return `📅 Earnings: ${earnings.recommendation || ""}${surprise}${reaction}`;
          }
          return null;
        };

        const content = findMatch();
        setTooltipContent(content);
        if (content && point) {
          setTooltipPos({ x: point.x + 12, y: point.y - 10 });
        }
      };
      chart.subscribeCrosshairMove(crosshairHandler);
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (crosshairHandler && chartRef.current) {
        chartRef.current.unsubscribeCrosshairMove(crosshairHandler);
      }
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      priceLinesRef.current = [];
      setTooltipContent(null);
    };
  }, [ohlcvData, overlayData, expectedMovePct, currentPrice]);

  useEffect(() => {
    if (aiLevels && candleSeriesRef.current) {
      drawAiLevels(candleSeriesRef.current, aiLevels, priceLinesRef, expectedMovePct, currentPrice);
    }
  }, [aiLevels, expectedMovePct, currentPrice]);

  const runAiAnalysis = useCallback(async () => {
    setLoadingAi(true);
    setAiError(null);
    try {
      const response = await api.getChartAnalysis(ticker);
      setAiLevels({
        support_levels: response.support_levels || [],
        resistance_levels: response.resistance_levels || [],
        entry_zone: response.entry_zone || null,
        stop_loss: response.stop_loss ?? null,
        target_1: response.target_1 ?? null,
        target_2: response.target_2 ?? null,
        analysis_text: response.analysis_text || "",
        bias: response.bias || "neutral",
        key_risk: response.key_risk || "",
        error: response.error ?? false,
      });
    } catch (error) {
      console.error("AI analysis error", error);
      setAiError("KI-Analyse fehlgeschlagen");
    } finally {
      setLoadingAi(false);
    }
  }, [ticker]);

  const renderBiasBadge = () => {
    if (!aiLevels) return null;
    let className = "bg-gray-500/20 text-gray-300";
    let icon = <Minus size={12} />;
    if (aiLevels.bias === "bullish") {
      className = "bg-emerald-500/20 text-emerald-400";
      icon = <TrendingUp size={12} />;
    } else if (aiLevels.bias === "bearish") {
      className = "bg-rose-500/20 text-rose-400";
      icon = <TrendingDown size={12} />;
    }
    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${className}`}>
        {icon}
        {aiLevels.bias?.toUpperCase() || "NEUTRAL"}
      </span>
    );
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[var(--text-muted)]">
          <LineChart size={16} />
          <h2 className="text-sm font-semibold uppercase tracking-[0.3em]">Chartanalyse</h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex overflow-hidden rounded-lg border border-[var(--border)]">
            {(
              [
                { value: "3mo", label: "3M" },
                { value: "6mo", label: "6M" },
                { value: "1y",  label: "1J" },
                { value: "2y",  label: "2J" },
              ] as const
            ).map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setActiveTimeframe(value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  activeTimeframe === value
                    ? "bg-[var(--accent-blue)] text-white"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                }`}
              >
                {label}
                {value === "2y" && (
                  <span className="ml-1 text-[9px] opacity-70">W</span>
                )}
              </button>
            ))}
          </div>
          <span className="text-[10px] text-[var(--text-muted)] self-center">
            {activeTimeframe === "2y" ? "Wochenkerzen" : "Tageskerzen"}
          </span>
          <button
            onClick={runAiAnalysis}
            disabled={loadingAi || loadingOhlcv}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {loadingAi ? <Loader2 size={14} className="animate-spin" /> : <LineChart size={14} />}
            {loadingAi ? "Analysiere..." : "KI-Analyse"}
          </button>
        </div>
      </div>

      <div className="relative">
        {loadingOhlcv && (
          <div className="flex h-[420px] items-center justify-center rounded-xl bg-[var(--bg-tertiary)]">
            <Loader2 size={24} className="animate-spin text-[var(--text-muted)]" />
          </div>
        )}
        {!loadingOhlcv && (!ohlcvData || ohlcvData.error || !ohlcvData.candles.length) && (
          <div className="flex h-[420px] items-center justify-center rounded-xl bg-[var(--bg-tertiary)] text-sm text-[var(--text-muted)]">
            Keine Chart-Daten verfügbar.
          </div>
        )}
        <div ref={chartContainerRef} className={loadingOhlcv ? "hidden" : "block"} />

        {tooltipContent && (
          <div
            className="pointer-events-none absolute z-10 max-w-xs rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2 text-xs text-[var(--text-primary)] shadow-lg"
            style={{ left: tooltipPos.x, top: tooltipPos.y }}
          >
            {tooltipContent}
          </div>
        )}
      </div>

      {!loadingOhlcv && (
        <div className="flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-6 border-t-2 border-dashed border-blue-500" /> SMA 50
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-6 border-t-2 border-dashed border-purple-500" /> SMA 200
          </span>
          <span className="flex items-center gap-1.5">
            <ChevronUp size={12} className="text-blue-400" /> Earnings
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-red-400">⚠</span> Torpedo Alert
          </span>
          <span className="flex items-center gap-1.5">
            <ChevronDown size={12} className="text-amber-400" /> Narrative Shift
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-green-400">▲</span> Insider Kauf
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-red-400">▼</span> Insider Verkauf
          </span>
        </div>
      )}

      {aiError && <p className="text-sm text-[var(--accent-red)]">{aiError}</p>}

      {aiLevels && (
        <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4">
          <div className="flex flex-wrap items-center gap-3">
            {renderBiasBadge()}
            {aiLevels.entry_zone && (
              <span className="text-xs text-[var(--text-secondary)]">
                Entry: <span className="font-semibold text-[var(--text-primary)]">${aiLevels.entry_zone.low.toFixed(2)} – ${aiLevels.entry_zone.high.toFixed(2)}</span>
              </span>
            )}
            {aiLevels.stop_loss && (
              <span className="text-xs text-[var(--text-secondary)]">
                Stop: <span className="font-semibold text-rose-400">${aiLevels.stop_loss.toFixed(2)}</span>
              </span>
            )}
            {aiLevels.target_1 && (
              <span className="text-xs text-[var(--text-secondary)]">
                T1: <span className="font-semibold text-emerald-400">${aiLevels.target_1.toFixed(2)}</span>
              </span>
            )}
            {aiLevels.target_2 && (
              <span className="text-xs text-[var(--text-secondary)]">
                T2: <span className="font-semibold text-emerald-400">${aiLevels.target_2.toFixed(2)}</span>
              </span>
            )}
          </div>

          {aiLevels.analysis_text && (
            <p className="text-sm text-[var(--text-primary)] leading-relaxed">{aiLevels.analysis_text}</p>
          )}

          {aiLevels.key_risk && (
            <p className="text-xs text-[var(--text-secondary)]">
              <span className="font-semibold text-amber-400">Risiko: </span>
              {aiLevels.key_risk}
            </p>
          )}

          {aiLevels.error && (
            <p className="text-xs text-amber-400">⚠️ JSON-Parse-Fehler — Fallback-Levels aktiv</p>
          )}
        </div>
      )}
    </div>
  );
}
