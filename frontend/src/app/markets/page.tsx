"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  Activity, 
  Globe, 
  Zap, 
  BarChart3,
  Newspaper,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Timer,
  Info,
  Brain,
  Eye,
  EyeOff,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";

// Types
type IndexData = {
  name: string;
  price?: number;
  change_1d_pct?: number;
  change_5d_pct?: number;
  change_1m_pct?: number;
  rsi_14?: number;
  trend?: string;
  above_sma50?: boolean;
  above_sma200?: boolean;
  error?: string;
};

type MarketOverview = {
  timestamp: string;
  indices: Record<string, IndexData>;
  sector_ranking_5d: Array<{ symbol: string; name: string; perf_5d: number }>;
  macro: Record<string, IndexData>;
};

type MarketBreadth = {
  pct_above_sma50: number;
  pct_above_sma200: number;
  breadth_signal: string;
  advancing: number;
  declining: number;
  sample_size: number;
  breadth_index: string;
  pct_above_sma50_5d_ago?: number | null;
  pct_above_sma50_20d_ago?: number | null;
  breadth_trend_5d?: string | null;
  error?: string;
};

type IntermarketAsset = {
  name: string;
  price: number;
  change_1d: number;
  change_1w: number;
  change_1m: number;
  above_sma20: boolean;
  trend_1m: string;
};

type IntermarketData = {
  assets: Record<string, IntermarketAsset>;
  signals: {
    risk_appetite?: string;
    vix_structure?: string;
    vix_note?: string;
    credit_signal?: string;
    credit_note?: string;
    energy_stress?: string;
    energy_note?: string;
    stagflation_warning?: boolean;
    stagflation_note?: string;
  };
};

type MacroSnapshot = {
  regime?: string;
  fed_rate?: number;
  vix?: number;
  credit_spread_bps?: number;
  yield_curve_10y_2y?: number;
  yield_curve?: string;
  dxy?: number;
};

type NewsSentimentItem = {
  headline: string;
  category: string;
  source: string;
  timestamp: number;
  url: string;
  sentiment_score: number;
  origin?: string;
};

type NewsSentimentData = {
  headlines: NewsSentimentItem[];
  category_sentiment: Record<string, { score: number; count: number; label: string }>;
  total_analyzed: number;
  fetched_at: string;
  overall_sentiment?: {
    score: number;
    label: string;
    bullish: number;
    bearish: number;
    neutral: number;
    sample_size: number;
    source_counts?: Record<string, number>;
  };
  source_breakdown?: Record<string, { count: number; score: number; label: string }>;
};

type EconomicEvent = {
  title: string;
  date: string;
  impact: string;
  country: string;
  actual?: string;
  estimate?: string;
};

type EconomicCalendar = {
  events: EconomicEvent[];
};

type MarketAudit = {
  status: string;
  report?: string;
  generated_at?: string;
  message?: string;
};

type FearGreedData = {
  score: number;
  label: string;
  components: Record<string, {
    value: number;
    score: number;
    weight: number;
    label: string;
  }>;
  coverage: number;
};

// Composite Regime Calculation
function calcCompositeRegime(
  vix?: number,
  creditSpread?: number,
  yieldSpread?: number,
  breadthPct?: number,
  riskAppetite?: string,
  vixStructure?: string
): {
  score: number;
  regime: "Risk-On" | "Neutral" | "Risk-Off";
  factors: Array<{
    name: string;
    signal: number;
    weight: number;
    weighted: number;
  }>;
  dominant: string;
} {
  const factors = [];
  
  // VIX Factor (0-2, inverted: low VIX = positive)
  if (vix !== undefined && vix !== null) {
    const signal = vix < 15 ? 2 : vix < 25 ? 1 : vix < 35 ? 0 : -1;
    const weight = 0.25;
    factors.push({ name: "VIX", signal, weight, weighted: signal * weight });
  }
  
  // Credit Spread Factor (0-2, inverted: low spread = positive)
  if (creditSpread !== undefined && creditSpread !== null) {
    const signal = creditSpread < 300 ? 2 : creditSpread < 400 ? 1 : creditSpread < 500 ? 0 : -1;
    const weight = 0.20;
    factors.push({ name: "Credit Spread", signal, weight, weighted: signal * weight });
  }
  
  // Yield Curve Factor (0-2, inverted: positive spread = positive)
  if (yieldSpread !== undefined && yieldSpread !== null) {
    const signal = yieldSpread > 0.5 ? 2 : yieldSpread > 0 ? 1 : yieldSpread > -0.5 ? 0 : -1;
    const weight = 0.15;
    factors.push({ name: "Yield Curve", signal, weight, weighted: signal * weight });
  }
  
  // Market Breadth Factor (0-2)
  if (breadthPct !== undefined && breadthPct !== null) {
    const signal = breadthPct > 70 ? 2 : breadthPct > 50 ? 1 : breadthPct > 30 ? 0 : -1;
    const weight = 0.20;
    factors.push({ name: "Market Breadth", signal, weight, weighted: signal * weight });
  }
  
  // Risk Appetite Factor (0-2)
  if (riskAppetite) {
    const signal = riskAppetite === "risk_on" ? 2 : riskAppetite === "mixed" ? 0 : -1;
    const weight = 0.10;
    factors.push({ name: "Risk Appetite", signal, weight, weighted: signal * weight });
  }
  
  // VIX Structure Factor (0-2)
  if (vixStructure) {
    const signal = vixStructure === "contango" ? 1 : vixStructure === "flat" ? 0 : -1;
    const weight = 0.10;
    factors.push({ name: "VIX Structure", signal, weight, weighted: signal * weight });
  }
  
  // Calculate weighted score
  const score = factors.reduce((sum, f) => sum + f.weighted, 0);
  
  // Determine regime
  let regime: "Risk-On" | "Neutral" | "Risk-Off";
  if (score >= 1.0) {
    regime = "Risk-On";
  } else if (score <= -0.5) {
    regime = "Risk-Off";
  } else {
    regime = "Neutral";
  }
  
  // Find dominant factor
  const dominant = factors.reduce((prev, current) => 
    Math.abs(current.weighted) > Math.abs(prev.weighted) ? current : prev
  , factors[0])?.name || "Unknown";
  
  return { score, regime, factors, dominant };
}

// Regime Header Component
function RegimeHeader({ data }: { data: {
  vix?: number;
  creditSpread?: number;
  yieldSpread?: number;
  breadthPct?: number;
  riskAppetite?: string;
  vixStructure?: string;
}}) {
  const [expanded, setExpanded] = useState(false);
  
  const composite = calcCompositeRegime(
    data.vix,
    data.creditSpread,
    data.yieldSpread,
    data.breadthPct,
    data.riskAppetite,
    data.vixStructure
  );
  
  const regimeColors = {
    "Risk-On": "bg-green-600/20 border-green-500/50 text-green-400",
    "Neutral": "bg-amber-600/20 border-amber-500/50 text-amber-400",
    "Risk-Off": "bg-red-600/20 border-red-500/50 text-red-400"
  };
  
  const regimeTextColors = {
    "Risk-On": "text-green-400",
    "Neutral": "text-amber-400", 
    "Risk-Off": "text-red-400"
  };
  
  return (
    <div className={`card p-6 border-2 ${regimeColors[composite.regime]}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Brain size={24} className={regimeTextColors[composite.regime]} />
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">
              Composite Regime: <span className={regimeTextColors[composite.regime]}>{composite.regime}</span>
            </h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Score: {composite.score >= 0 ? "+" : ""}{composite.score.toFixed(1)} | Dominant: {composite.dominant}
            </p>
          </div>
        </div>
        
        {/* Mini-Dots */}
        <div className="flex items-center gap-2">
          {composite.factors.map((factor, idx) => {
            const dotColor = factor.signal >= 1 ? "bg-green-500" : 
                           factor.signal <= -1 ? "bg-red-500" : "bg-amber-500";
            return (
              <div
                key={idx}
                className={`w-2 h-2 rounded-full ${dotColor}`}
                title={`${factor.name}: ${factor.signal}`}
              />
            );
          })}
        </div>
      </div>
      
      {/* Expandable Details */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm text-[var(--accent-blue)] hover:underline"
        >
          {expanded ? <><EyeOff size={16} /> Details ausblenden</> : <><Eye size={16} /> Details anzeigen</>}
        </button>
      </div>
      
      {expanded && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {composite.factors.map((factor, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-[var(--bg-tertiary)]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">{factor.name}</span>
                  <span className="text-xs px-2 py-1 rounded bg-[var(--bg-secondary)] text-[var(--text-muted)]">
                    {(factor.weight * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    factor.signal >= 1 ? "bg-green-500" : 
                    factor.signal <= -1 ? "bg-red-500" : "bg-amber-500"
                  }`} />
                  <span className="text-sm font-mono text-[var(--text-primary)]">
                    {factor.signal >= 0 ? "+" : ""}{factor.signal}
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">
                    ({factor.weighted >= 0 ? "+" : ""}{factor.weighted.toFixed(2)})
                  </span>
                </div>
              </div>
            ))}
          </div>
          
          <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
            <p className="text-xs text-[var(--text-secondary)]">
              <strong>Methodik:</strong> Gewichteter Durchschnitt von 6 Marktfaktoren (VIX, Credit Spread, Yield Curve, 
              Market Breadth, Risk Appetite, VIX Structure). Score ≥1.0 = Risk-On, ≤-0.5 = Risk-Off, sonst Neutral.
              Dominant = Faktor mit höchstem absoluten Gewichtungsbeitrag.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper functions
function TrendIcon({ value }: { value?: number }) {
  if (value === undefined || value === null) return <Minus size={14} className="text-[var(--text-muted)]" />;
  return value >= 0 ? (
    <TrendingUp size={14} className="text-[var(--accent-green)]" />
  ) : (
    <TrendingDown size={14} className="text-[var(--accent-red)]" />
  );
}

function formatPct(value?: number, fallback = "--") {
  if (value === undefined || value === null || Number.isNaN(value)) return fallback;
  const formatted = value.toFixed(2).replace("-0.00", "0.00");
  return `${formatted}%`;
}

function BlockError({ title }: { title: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <p className="mb-2 text-xs uppercase tracking-widest text-[var(--text-muted)]">{title}</p>
      <p className="text-sm text-[var(--text-muted)]">Daten nicht verfügbar</p>
    </div>
  );
}

function RSIBar({ value }: { value?: number }) {
  if (value === null || value === undefined) return <span className="text-muted">—</span>;
  const color = value > 70 ? "var(--accent-red)" : value < 30 ? "var(--accent-green)" : "var(--accent-blue)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded bg-[var(--bg-elevated)]">
        <div
          className="h-full rounded"
          style={{
            width: `${Math.min(100, value)}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }}>
        {value.toFixed(0)}
      </span>
    </div>
  );
}

function getSectorColor(perf: number): string {
  if (perf >= 2) return "bg-green-600/80 text-white";
  if (perf >= 0.5) return "bg-green-600/30 text-green-200";
  if (perf >= -0.5) return "bg-[var(--bg-tertiary)] text-[var(--text-secondary)]";
  if (perf >= -2) return "bg-red-600/30 text-red-200";
  return "bg-red-600/80 text-white";
}

function getTimeDelta(timestamp: string): string {
  const now = new Date();
  const dataTime = new Date(timestamp);
  const deltaMs = now.getTime() - dataTime.getTime();
  const deltaMins = Math.floor(deltaMs / 60000);
  
  if (deltaMins < 1) return "jetzt";
  if (deltaMins < 60) return `vor ${deltaMins} min`;
  const deltaHours = Math.floor(deltaMins / 60);
  if (deltaHours < 24) return `vor ${deltaHours} h`;
  const deltaDays = Math.floor(deltaHours / 24);
  return `vor ${deltaDays} d`;
}

function isStale(timestamp: string, maxMinutes: number): boolean {
  const now = new Date();
  const dataTime = new Date(timestamp);
  const deltaMs = now.getTime() - dataTime.getTime();
  const deltaMins = Math.floor(deltaMs / 60000);
  return deltaMins > maxMinutes;
}


function BlockHeaderBadge({ block, cadence }: { block: string; cadence: string }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <span className="rounded-full bg-[var(--bg-tertiary)] px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">
        {block}
      </span>
      <span className="text-[11px] uppercase tracking-[0.18em] text-[var(--accent-blue)]">
        {cadence}
      </span>
    </div>
  );
}

// Block 1: Global Indices
function GlobalIndicesBlock({ data, timestamp, indexAnalysis, analysisPending, onAnalyze, onRemoveAnalysis }: { 
  data?: MarketOverview; 
  timestamp?: string;
  indexAnalysis?: Record<string, any>;
  analysisPending?: Record<string, boolean>;
  onAnalyze?: (symbol: string) => void;
  onRemoveAnalysis?: (symbol: string) => void;
}) {
  if (!data?.indices) return <BlockError title="Globale Indizes" />;
  
  const indices = [
    "SPY", "QQQ", "DIA", "IWM", "^GDAXI", "^STOXX50E", "^N225", "URTH"
  ];
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 1" cadence="60s Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Globe size={18} />
          Globale Indizes
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 60) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>
      
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {indices.map((symbol) => {
          const item = data.indices[symbol];
          if (!item || item.error) return null;
          
          return (
            <div key={symbol} className="p-3 rounded-lg bg-[var(--bg-tertiary)]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--text-muted)]">{symbol}</span>
                <TrendIcon value={item.change_1d_pct} />
              </div>
              <div className="text-lg font-bold text-[var(--text-primary)] mb-1">
                ${item.price?.toFixed(2) || "--"}
              </div>
              <div className={`text-sm font-medium ${
                item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"
              }`}>
                {formatPct(item.change_1d_pct)}
              </div>
              {/* 5T + 20T Performance */}
              <div className="flex gap-2 mt-1.5">
                <span className={`text-[10px] font-mono ${
                  (item.change_5d_pct ?? 0) >= 0
                    ? "text-[var(--accent-green)]"
                    : "text-[var(--accent-red)]"
                }`}>
                  5T: {item.change_5d_pct != null
                    ? `${item.change_5d_pct >= 0 ? "+" : ""}${item.change_5d_pct.toFixed(1)}%` 
                    : "—"}
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">·</span>
                <span className={`text-[10px] font-mono ${
                  (item.change_1m_pct ?? 0) >= 0
                    ? "text-[var(--accent-green)]"
                    : "text-[var(--accent-red)]"
                }`}>
                  20T: {item.change_1m_pct != null
                    ? `${item.change_1m_pct >= 0 ? "+" : ""}${item.change_1m_pct.toFixed(1)}%` 
                    : "—"}
                </span>
              </div>
              <div className="text-xs text-[var(--text-muted)] mt-1">
                {item.name}
              </div>
              
              {/* Analyse-Button */}
              {onAnalyze && !indexAnalysis?.[symbol] && (
                <div className="mt-2 flex gap-1">
                  <button
                    onClick={() => onAnalyze(symbol)}
                    disabled={analysisPending?.[symbol]}
                    className="flex-1 text-[10px] rounded
                               border border-[var(--border)]
                               px-2 py-1 text-[var(--text-muted)]
                               hover:text-[var(--accent-blue)]
                               hover:border-[var(--accent-blue)]
                               disabled:opacity-50 transition-colors"
                  >
                    {analysisPending?.[symbol]
                      ? "Analysiere…"
                      : "⚡ Chart"}
                  </button>
                  <Link
                    href={`/research/${symbol}`}
                    className="flex-1 text-[10px] rounded
                             border border-[var(--border)]
                             px-2 py-1 text-[var(--text-muted)]
                             hover:text-[var(--accent-green)]
                             hover:border-[var(--accent-green)]
                             transition-colors text-center"
                  >
                    Research
                  </Link>
                </div>
              )}

              {/* Analyse-Ergebnis */}
              {indexAnalysis?.[symbol] && !indexAnalysis[symbol].error && (
                <div className="mt-2 rounded bg-[var(--bg-tertiary)]
                                px-2.5 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-semibold ${
                      indexAnalysis[symbol].bias === "bullish"
                        ? "text-[var(--accent-green)]"
                      : indexAnalysis[symbol].bias === "bearish"
                        ? "text-[var(--accent-red)]"
                      : "text-amber-400"
                    }`}>
                      {indexAnalysis[symbol].bias?.toUpperCase() ?? "—"}
                    </span>
                    <button
                      onClick={() => onRemoveAnalysis?.(symbol)}
                      className="text-[10px] text-[var(--text-muted)]
                                 hover:text-[var(--text-primary)]"
                    >
                      ✕
                    </button>
                  </div>
                  {indexAnalysis[symbol].analysis_text && (
                    <p className="text-[10px] text-[var(--text-secondary)]
                           leading-relaxed">
                      {indexAnalysis[symbol].analysis_text}
                    </p>
                  )}
                  {indexAnalysis[symbol].key_risk && (
                    <p className="text-[10px] text-[var(--accent-red)] mt-1">
                      ⚠ {indexAnalysis[symbol].key_risk}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function VIXDetailBlock({
  intermarket,
  macro,
}: {
  intermarket?: IntermarketData;
  macro?: MacroSnapshot;
}) {
  if (!macro?.vix) return null;

  const vixAsset = intermarket?.assets?.["^VIX"];
  const vix3mAsset = intermarket?.assets?.["^VIX3M"];
  const vixStructure = intermarket?.signals?.vix_structure;
  const vixNote = intermarket?.signals?.vix_note;

  const vixVal = macro.vix;
  const vix3mVal = vix3mAsset?.price;

  // VIX-Einordnung
  const vixLabel =
    vixVal > 35 ? "Panik" :
    vixVal > 25 ? "Stress" :
    vixVal > 15 ? "Normal" :
    "Euphorie";
  const vixColor =
    vixVal > 35 ? "text-[var(--accent-red)]" :
    vixVal > 25 ? "text-amber-400" :
    vixVal > 15 ? "text-[var(--accent-green)]" :
    "text-[var(--accent-green)]";

  // Term Structure Badge
  const structureBadge =
    vixStructure === "backwardation"
      ? { label: "Backwardation — Kurzfrist-Panik", color: "bg-red-900/30 text-red-400" }
      : vixStructure === "contango"
      ? { label: "Contango — Markt ruhig", color: "bg-green-900/30 text-green-400" }
      : { label: "VIX-Kurve flach", color: "bg-[var(--bg-tertiary)] text-[var(--text-muted)]" };

  return (
    <div className="card p-4 mt-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-[var(--text-primary)]">
          VIX Detail
        </h4>
        <span className={`text-xs px-2 py-0.5 rounded-full ${structureBadge.color}`}>
          {structureBadge.label}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div className="text-[10px] text-[var(--text-muted)] mb-1">VIX (30T)</div>
          <div className={`text-xl font-bold font-mono ${vixColor}`}>
            {vixVal.toFixed(1)}
          </div>
          <div className="text-[10px] text-[var(--text-muted)] mt-1">{vixLabel}</div>
        </div>

        <div className="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div className="text-[10px] text-[var(--text-muted)] mb-1">VIX3M (90T)</div>
          <div className="text-xl font-bold font-mono text-[var(--text-primary)]">
            {vix3mVal != null ? vix3mVal.toFixed(1) : "—"}
          </div>
          <div className="text-[10px] text-[var(--text-muted)] mt-1">90-Tage</div>
        </div>

        <div className="p-3 rounded-lg bg-[var(--bg-tertiary)] text-center">
          <div className="text-[10px] text-[var(--text-muted)] mb-1">1W Änderung</div>
          <div className={`text-xl font-bold font-mono ${
            (vixAsset?.change_1w ?? 0) > 0
              ? "text-[var(--accent-red)]"
              : "text-[var(--accent-green)]"
          }`}>
            {vixAsset?.change_1w != null
              ? `${vixAsset.change_1w >= 0 ? "+" : ""}${vixAsset.change_1w.toFixed(1)}%` 
              : "—"}
          </div>
          <div className="text-[10px] text-[var(--text-muted)] mt-1">
            {(vixAsset?.change_1w ?? 0) > 10
              ? "stark steigend"
              : (vixAsset?.change_1w ?? 0) > 0
              ? "leicht steigend"
              : (vixAsset?.change_1w ?? 0) < -10
              ? "stark fallend"
              : "leicht fallend"}
          </div>
        </div>
      </div>

      {vixNote && (
        <p className="text-xs text-[var(--text-secondary)] bg-[var(--bg-tertiary)]
                      rounded px-3 py-2">
          {vixNote}
        </p>
      )}
    </div>
  );
}

// Block 2: Sector Rotation
function SectorRotationBlock({ data, timestamp }: { data?: MarketOverview; timestamp?: string }) {
  if (!data?.sector_ranking_5d) return <BlockError title="Sektor-Rotation" />;
  
  const sectors = data.sector_ranking_5d;
  const top3 = sectors.slice(0, 3);
  const bottom3 = sectors.slice(-3).reverse();
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 2" cadence="60s Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <BarChart3 size={18} />
          Sektor-Rotation (5d)
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 60) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-3 md:grid-cols-4 gap-2 mb-4">
        {sectors.map((sector) => (
          <div 
            key={sector.symbol}
            className={`p-2 rounded-lg text-center ${getSectorColor(sector.perf_5d)}`}
          >
            <div className="text-[10px] font-bold leading-tight">
              {sector.symbol}
            </div>
            <div className="text-[9px] text-[var(--text-muted)] leading-tight">
              {sector.name}
            </div>
            <div className={`text-xs font-bold mt-1 ${
              sector.perf_5d >= 0
                ? "text-[var(--accent-green)]"
                : "text-[var(--accent-red)]"
            }`}>
              {sector.perf_5d >= 0 ? "+" : ""}{sector.perf_5d.toFixed(1)}%
            </div>
          </div>
        ))}
      </div>
      
      <div className="text-xs text-[var(--text-secondary)]">
        <span className="text-[var(--accent-green)]">Top: {top3.map(s => s.symbol).join(", ")}</span>
        <span className="mx-2">|</span>
        <span className="text-[var(--accent-red)]">Bottom: {bottom3.map(s => s.symbol).join(", ")}</span>
      </div>
      {(data as any).rotation_story && (
        <div className={`mt-3 text-xs px-3 py-2 rounded-lg ${
          (data as any).rotation_signal === "risk_off"
            ? "bg-red-900/20 text-red-400"
            : (data as any).rotation_signal === "risk_on"
            ? "bg-green-900/20 text-green-400"
            : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
        }`}>
          {(data as any).rotation_story}
        </div>
      )}
    </div>
  );
}

// Block 3: Market Breadth
function MarketBreadthBlock({ data, timestamp }: { data?: MarketBreadth; timestamp?: string }) {
  if (!data || data.error) return <BlockError title="Marktbreite" />;
  
  const getColor = (val: number) => {
    if (val >= 70) return "var(--accent-green)";
    if (val >= 40) return "var(--accent-amber)";
    return "var(--accent-red)";
  };
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 3" cadence="5min Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Activity size={18} />
          Marktbreite ({data.breadth_index})
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 30) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-2 gap-6 mb-4">
        <div>
          <div className="text-sm text-[var(--text-muted)] mb-2">Über SMA50</div>
          <div className="relative h-24">
            <svg viewBox="0 0 100 50" className="w-full h-full">
              <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="var(--bg-tertiary)" strokeWidth="8" />
              <path 
                d="M 10 50 A 40 40 0 0 1 90 50" 
                fill="none" 
                stroke={getColor(data.pct_above_sma50)} 
                strokeWidth="8"
                strokeDasharray={`${(data.pct_above_sma50 / 100) * 126} 126`}
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex items-end justify-center pb-2">
              <span className="text-2xl font-bold" style={{ color: getColor(data.pct_above_sma50) }}>
                {data.pct_above_sma50}%
              </span>
            </div>
          </div>
        </div>
        <div>
          <div className="text-sm text-[var(--text-muted)] mb-2">Über SMA200</div>
          <div className="relative h-24">
            <svg viewBox="0 0 100 50" className="w-full h-full">
              <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="var(--bg-tertiary)" strokeWidth="8" />
              <path 
                d="M 10 50 A 40 40 0 0 1 90 50" 
                fill="none" 
                stroke={getColor(data.pct_above_sma200)} 
                strokeWidth="8"
                strokeDasharray={`${(data.pct_above_sma200 / 100) * 126} 126`}
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex items-end justify-center pb-2">
              <span className="text-2xl font-bold" style={{ color: getColor(data.pct_above_sma200) }}>
                {data.pct_above_sma200}%
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="text-xs text-[var(--text-muted)]">
        <div className="flex justify-between">
          <span>Advancing: <span className="text-[var(--accent-green)] font-medium">{data.advancing}</span></span>
          <span>Declining: <span className="text-[var(--accent-red)] font-medium">{data.declining}</span></span>
        </div>
        <div className="mt-2 text-center">
          Signal: <span className={`font-semibold ${
            data.breadth_signal === "stark" ? "text-[var(--accent-green)]" :
            data.breadth_signal === "schwach" ? "text-[var(--accent-red)]" :
            "text-[var(--accent-amber)]"
          }`}>{data.breadth_signal.toUpperCase()}</span>
        </div>
      </div>
      
      {/* Enhanced Trend-Delta wenn verfügbar */}
      {(data.pct_above_sma50_5d_ago != null
        || data.pct_above_sma50_20d_ago != null) && (
        <div className="flex gap-4 text-xs text-[var(--text-muted)] mt-2">
          {data.pct_above_sma50_5d_ago != null && (
            <span>
              vor 5T: {data.pct_above_sma50_5d_ago.toFixed(1)}%
              <span className={
                data.pct_above_sma50
                  > data.pct_above_sma50_5d_ago
                  ? " text-[var(--accent-green)]"
                  : " text-[var(--accent-red)]"
              }>
                {" "}({(data.pct_above_sma50
                  - data.pct_above_sma50_5d_ago
                ).toFixed(1)}pp)
              </span>
            </span>
          )}
          {data.pct_above_sma50_20d_ago != null && (
            <span>
              vor 20T: {data.pct_above_sma50_20d_ago.toFixed(1)}%
            </span>
          )}
          {data.breadth_trend_5d && (
            <span className={
              data.breadth_trend_5d === "steigend"
                ? "text-[var(--accent-green)]"
              : data.breadth_trend_5d === "fallend"
                ? "text-[var(--accent-red)]"
                : "text-[var(--text-muted)]"
            }>
              Trend: {data.breadth_trend_5d}
            </span>
          )}
        </div>
      )}

      {/* Wenn kein Delta: Hinweis */}
      {data.pct_above_sma50_5d_ago == null && data.pct_above_sma50_20d_ago == null && (
        <div className="mt-2 text-[10px] text-center text-[var(--text-muted)]">
          Verlauf in Kürze verfügbar
        </div>
      )}
    </div>
  );
}

// Block 4: Macro Dashboard
function MacroDashboardBlock({ data, timestamp }: { data?: MacroSnapshot; timestamp?: string }) {
  if (!data) return <BlockError title="Makro-Dashboard" />;
  
  const cards = [
    { 
      label: "Fed Rate", 
      value: data.fed_rate !== undefined ? `${data.fed_rate.toFixed(2)}%` : "--",
      note: "Leitzins"
    },
    { 
      label: "VIX", 
      value: data.vix !== undefined ? data.vix.toFixed(2) : "--",
      note: data.vix && data.vix > 25 ? "Stress" : data.vix && data.vix > 15 ? "Normal" : "Euphorie",
      color: data.vix && data.vix > 25 ? "text-red-400" : data.vix && data.vix > 15 ? "text-amber-400" : "text-green-400"
    },
    { 
      label: "Credit Spread", 
      value: data.credit_spread_bps !== undefined ? `${data.credit_spread_bps.toFixed(0)}bp` : "--",
      note: data.credit_spread_bps && data.credit_spread_bps > 500 ? "Stress" : 
            data.credit_spread_bps && data.credit_spread_bps > 350 ? "Erhöht" : "Gesund",
      color: data.credit_spread_bps && data.credit_spread_bps > 500 ? "text-red-400" : 
            data.credit_spread_bps && data.credit_spread_bps > 350 ? "text-amber-400" : "text-green-400"
    },
    { 
      label: "Yield Curve", 
      value: data.yield_curve_10y_2y !== undefined ? `${data.yield_curve_10y_2y.toFixed(2)}%` : "--",
      note: data.yield_curve === "inverted" ? "Rezessionsrisiko" : 
            data.yield_curve === "flat" ? "Warnung" : "Normal",
      color: data.yield_curve === "inverted" ? "text-red-400" : 
            data.yield_curve === "flat" ? "text-amber-400" : "text-green-400"
    },
  ];
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 4" cadence="30min Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Activity size={18} />
          Makro-Dashboard
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 1800) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="p-4 rounded-lg bg-[var(--bg-tertiary)]">
            <p className="text-xs text-[var(--text-muted)] mb-1">{card.label}</p>
            <p className={`text-xl font-bold ${card.color || "text-[var(--text-primary)]"}`}>
              {card.value}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{card.note}</p>
          </div>
        ))}
      </div>
      
      {data.regime && (
        <div className="mt-4 p-3 rounded-lg bg-[var(--bg-tertiary)]">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-[var(--accent-blue)]" />
            <span className="text-xs text-[var(--text-muted)]">
              FRED Regime: {data.regime.toUpperCase()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// Block 5: Cross-Asset Signals
function CrossAssetBlock({ data, timestamp }: { data?: IntermarketData; timestamp?: string }) {
  if (!data?.assets) return <BlockError title="Cross-Asset-Signale" />;
  
  const { assets, signals } = data;
  const displayAssets = ["GLD", "USO", "UUP", "TLT", "EEM", "HYG"];
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 5" cadence="10min Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Globe size={18} />
          Cross-Asset-Signale
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 600) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>
      
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Assets</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="pb-2">Asset</th>
                <th className="pb-2 text-right">1T%</th>
                <th className="pb-2 text-right">1W%</th>
                <th className="pb-2 text-right">1M%</th>
              </tr>
            </thead>
            <tbody>
              {displayAssets.map((symbol) => {
                const asset = assets[symbol];
                if (!asset) return null;
                return (
                  <tr key={symbol} className="border-t border-[var(--border)]">
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <TrendIcon value={asset.change_1d} />
                        <span className="font-medium">{symbol}</span>
                      </div>
                    </td>
                    <td className={`py-2 text-right font-medium ${
                      asset.change_1d >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"
                    }`}>
                      {formatPct(asset.change_1d)}
                    </td>
                    <td className={`py-2 text-right font-medium ${
                      (asset.change_1w ?? 0) >= 0
                        ? "text-[var(--accent-green)]"
                        : "text-[var(--accent-red)]"
                    }`}>
                      {asset.change_1w != null
                        ? `${asset.change_1w >= 0 ? "+" : ""}${asset.change_1w.toFixed(1)}%` 
                        : "—"}
                    </td>
                    <td className={`py-2 text-right font-medium ${
                      (asset.change_1m ?? 0) >= 0
                        ? "text-[var(--accent-green)]"
                        : "text-[var(--accent-red)]"
                    }`}>
                      {asset.change_1m != null
                        ? `${asset.change_1m >= 0 ? "+" : ""}${asset.change_1m.toFixed(1)}%` 
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Signale</h4>
          <div className="space-y-2">
            {signals.risk_appetite && (
              <div className={`p-3 rounded-lg ${
                signals.risk_appetite === "risk_on" ? "bg-green-500/10 border border-green-500/30" :
                signals.risk_appetite === "risk_off" ? "bg-red-500/10 border border-red-500/30" :
                "bg-amber-500/10 border border-amber-500/30"
              }`}>
                <div className="flex items-center gap-2">
                  {signals.risk_appetite === "risk_on" ? <TrendingUp size={16} className="text-green-500" /> :
                   signals.risk_appetite === "risk_off" ? <TrendingDown size={16} className="text-red-500" /> :
                   <Minus size={16} className="text-amber-500" />}
                  <span className="font-semibold text-[var(--text-primary)] text-sm">
                    Risk: {signals.risk_appetite.replace("_", "-").toUpperCase()}
                  </span>
                </div>
              </div>
            )}
            {signals.vix_structure && (
              <div className={`p-3 rounded-lg ${
                signals.vix_structure === "backwardation" ? "bg-red-500/10 border border-red-500/30" :
                "bg-green-500/10 border border-green-500/30"
              }`}>
                <div className="flex items-center gap-2">
                  {signals.vix_structure === "backwardation" ? <AlertTriangle size={16} className="text-red-500" /> :
                   <CheckCircle2 size={16} className="text-green-500" />}
                  <span className="font-semibold text-[var(--text-primary)] text-sm">
                    VIX: {signals.vix_structure.toUpperCase()}
                  </span>
                </div>
              </div>
            )}
            
            {/* Energie-Signal */}
            {signals.energy_stress && (
              <div className={`rounded-lg px-3 py-2 border ${
                signals.energy_stress === "schock"
                  ? "bg-red-900/30 border-red-700/50"
                  : signals.energy_stress === "erhöht"
                  ? "bg-amber-900/30 border-amber-700/50"
                  : signals.energy_stress === "entspannt"
                  ? "bg-green-900/30 border-green-700/50"
                  : "bg-[var(--bg-tertiary)] border-[var(--border)]"
              }`}>
                <div className={`text-xs font-semibold mb-0.5 ${
                  signals.energy_stress === "schock" ? "text-red-400" :
                  signals.energy_stress === "erhöht" ? "text-amber-400" :
                  signals.energy_stress === "entspannt" ? "text-green-400" :
                  "text-[var(--text-muted)]"
                }`}>
                  Energie: {signals.energy_stress.toUpperCase()}
                </div>
                {signals.energy_note && (
                  <div className="text-[10px] text-[var(--text-secondary)]">
                    {signals.energy_note}
                  </div>
                )}
              </div>
            )}

            {/* Stagflations-Warnung — nur wenn aktiv */}
            {signals.stagflation_warning && (
              <div className="rounded-lg px-3 py-2 border
                              bg-red-900/40 border-red-600/60 mt-2">
                <div className="text-xs font-bold text-red-400 mb-0.5">
                  ⚡ Stagflations-Warnung
                </div>
                <div className="text-[10px] text-red-300">
                  {signals.stagflation_note}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Block 6: Market-Sentiment
function NewsSentimentBlock({ data, timestamp }: { data?: NewsSentimentData; timestamp?: string }) {
  if (!data) return <BlockError title="Market-Sentiment" />;
  
  const getSentimentColor = (score: number) => {
    if (score > 0.15) return "text-green-500";
    if (score < -0.15) return "text-red-500";
    return "text-amber-500";
  };
  
  const getSentimentLabel = (score: number) => {
    if (score > 0.15) return "🟢 Bullish";
    if (score < -0.15) return "🔴 Bearish";
    return "🟡 Neutral";
  };

  const formatTimestamp = (timestamp: number) => {
    if (!timestamp) return "unbekannt";
    return new Intl.DateTimeFormat("de-DE", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(timestamp * 1000));
  };

  const overall = data.overall_sentiment;

  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 6" cadence="10min Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Newspaper size={18} />
          Market-Sentiment
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 600) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>

      {overall && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
          <div className="p-2 rounded bg-[var(--bg-tertiary)] text-center">
            <div className="text-xs text-[var(--text-muted)]">Gesamtsentiment</div>
            <div className={`text-sm font-bold ${getSentimentColor(overall.score)}`}>
              {overall.score.toFixed(2)}
            </div>
            <div className="text-xs text-[var(--text-muted)] capitalize">{overall.label}</div>
          </div>
          <div className="p-2 rounded bg-[var(--bg-tertiary)] text-center">
            <div className="text-xs text-[var(--text-muted)]">Bullish</div>
            <div className="text-sm font-bold text-green-500">{overall.bullish}</div>
            <div className="text-xs text-[var(--text-muted)]">letzte 24h</div>
          </div>
          <div className="p-2 rounded bg-[var(--bg-tertiary)] text-center">
            <div className="text-xs text-[var(--text-muted)]">Bearish</div>
            <div className="text-sm font-bold text-red-500">{overall.bearish}</div>
            <div className="text-xs text-[var(--text-muted)]">letzte 24h</div>
          </div>
          <div className="p-2 rounded bg-[var(--bg-tertiary)] text-center">
            <div className="text-xs text-[var(--text-muted)]">Abdeckung</div>
            <div className="text-sm font-bold text-[var(--text-primary)]">
              {overall.sample_size}
            </div>
            <div className="text-xs text-[var(--text-muted)]">
              F:{overall.source_counts?.finnhub ?? 0} · G:{overall.source_counts?.google_news ?? 0}
            </div>
          </div>
          <div className="p-2 rounded bg-[var(--bg-tertiary)] text-center">
            <div className="text-xs text-[var(--text-muted)]">Neutral</div>
            <div className="text-sm font-bold text-amber-500">{overall.neutral}</div>
            <div className="text-xs text-[var(--text-muted)]">letzte 24h</div>
          </div>
        </div>
      )}
      
      {/* Category Sentiment Summary */}
      {Object.keys(data.category_sentiment || {}).length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {Object.entries(data.category_sentiment).map(([category, sentiment]) => (
            <div key={category} className="p-2 rounded bg-[var(--bg-tertiary)] text-center">
              <div className="text-xs text-[var(--text-muted)] capitalize">{category.replace('_', ' ')}</div>
              <div className={`text-sm font-bold ${getSentimentColor(sentiment.score)}`}>
                {sentiment.score.toFixed(2)}
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                {sentiment.label} ({sentiment.count})
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* Headlines with Sentiment */}
      {Array.isArray(data.headlines) && data.headlines.length > 0 ? (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {data.headlines.slice(0, 10).map((item, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)] transition-colors">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-[var(--text-primary)] line-clamp-2 mb-1">
                    {item.headline}
                  </h4>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                    <span>{item.source}</span>
                    <span>•</span>
                    <span>{formatTimestamp(item.timestamp)}</span>
                    <span>•</span>
                    <span className="capitalize">{item.category.replace('_', ' ')}</span>
                    {item.origin && (
                      <>
                        <span>•</span>
                        <span className="capitalize">{item.origin.replace('_', ' ')}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-xs font-bold ${getSentimentColor(item.sentiment_score)}`}>
                    {getSentimentLabel(item.sentiment_score)}
                  </div>
                  <div className="text-xs text-[var(--text-muted)]">
                    {item.sentiment_score.toFixed(2)}
                  </div>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                    >
                      <ExternalLink size={12} />
                      Link
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-[var(--text-muted)]">
            Finnhub General News aktuell nicht verfügbar.
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            Mögliche Ursachen: Finnhub Free-Tier Rate-Limit (60 Calls/Min)
            oder keine neuen Artikel in den letzten 24h.
            Nächster Versuch in 10 Minuten.
          </p>
          <p className="text-xs text-[var(--text-secondary)]">
            Tipp: Watchlist-Ticker erhalten News über die
            FinBERT-Pipeline (n8n, alle 30 Min).
          </p>
        </div>
      )}
      
      <div className="mt-4 text-xs text-[var(--text-muted)] text-center">
        {data.total_analyzed} Headlines analysiert
      </div>
    </div>
  );
}

// Block 7: Economic Calendar
function EconomicCalendarBlock({ data, timestamp, onRefresh, loading }: { data?: EconomicCalendar; timestamp?: string; onRefresh?: () => void; loading?: boolean }) {
  if (!data?.events) return <BlockError title="Wirtschaftskalender" />;
  
  const getImpactColor = (impact: string) => {
    switch (impact.toLowerCase()) {
      case 'high': return 'bg-red-500/20 text-red-300 border border-red-500/30';
      case 'medium': return 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
      default: return 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]';
    }
  };
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 7" cadence="Manual / On-demand" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Timer size={18} />
          Wirtschaftskalender (48h)
        </h3>
        <div className="flex items-center gap-2">
          {timestamp && (
            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
              <Clock size={12} />
              <span>{getTimeDelta(timestamp)}</span>
            </div>
          )}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
              title="Kalender aktualisieren"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              {loading ? "Lade..." : "Aktualisieren"}
            </button>
          )}
        </div>
      </div>
      
      {data.events.length === 0 ? (
        <div className="text-center py-8 text-[var(--text-muted)]">
          <Timer size={32} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">Keine Events in den nächsten 48h</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {data.events.map((event, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-[var(--bg-tertiary)]">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-[var(--text-primary)] mb-1">
                    {event.title}
                  </h4>
                  <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                    <span>{new Date(event.date).toLocaleDateString('de-DE')}</span>
                    <span>•</span>
                    <span>{event.country}</span>
                  </div>
                  {/* Bei High-Impact-Events mit negativem Ergebnis: Fed-Kontext */}
                  {event.impact === "high" && event.actual && event.estimate && (
                    (() => {
                      const isMiss = parseFloat(event.actual) < parseFloat(event.estimate);
                      const isFedSensitive = ["CPI", "NFP", "Unemployment", "PCE", "PPI",
                        "GDP", "Retail Sales"].some(k =>
                          event.title.toUpperCase().includes(k.toUpperCase())
                        );
                      if (!isMiss || !isFedSensitive) return null;
                      return (
                        <span className="text-[10px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded ml-2">
                          Miss → Fed-Pivot möglich
                        </span>
                      );
                    })()
                  )}
                </div>
                <div className="text-right">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getImpactColor(event.impact)}`}>
                    {event.impact.toUpperCase()}
                  </span>
                  {(event.actual || event.estimate) && (
                    <div className="mt-1 text-xs">
                      {event.estimate && <span className="text-[var(--text-muted)]">Est: {event.estimate}</span>}
                      {event.actual && <span className="text-[var(--text-primary)] font-medium"> Act: {event.actual}</span>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Block 8: Market Audit (DeepSeek)
function MarketAuditBlock({ audit, onGenerate, loading }: { 
  audit?: MarketAudit; 
  onGenerate: () => void;
  loading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 8" cadence="Manual / On-demand" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Zap size={18} />
          KI-Markt-Audit
        </h3>
        {audit?.generated_at && (
          <span className="text-xs text-[var(--text-muted)]">
            {new Date(audit.generated_at).toLocaleString("de-DE")}
          </span>
        )}
      </div>

      {!audit?.report ? (
        <div className="text-center py-8">
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Regime-Einschätzung + Strategie-Empfehlung
          </p>
          <button
            onClick={onGenerate}
            disabled={loading}
            className="px-4 py-2 bg-[var(--accent-blue)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-2 mx-auto"
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Zap size={16} />}
            {loading ? "Generiere..." : "DeepSeek Audit generieren"}
          </button>
        </div>
      ) : (
        <div>
          <div className={`bg-[var(--bg-tertiary)] rounded-lg p-4 ${expanded ? "" : "max-h-48 overflow-hidden"}`}>
            <pre className="text-sm text-[var(--text-primary)] whitespace-pre-wrap font-sans">
              {audit.report}
            </pre>
          </div>
          <div className="flex items-center justify-between mt-4">
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-sm text-[var(--accent-blue)] hover:underline flex items-center gap-1"
            >
              {expanded ? <><ChevronUp size={16} /> Weniger</> : <><ChevronDown size={16} /> Mehr</>}
            </button>
            <button
              onClick={onGenerate}
              disabled={loading}
              className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Neu generieren
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Block 9: Macro Proxies
function MacroProxiesBlock({ data, timestamp }: { data?: MarketOverview; timestamp?: string }) {
  if (!data?.macro) return <BlockError title="Makro-Proxys" />;
  
  const proxies = [
    { symbol: "^VIX", name: "VIX" },
    { symbol: "TLT", name: "20Y+ Treasuries" },
    { symbol: "UUP", name: "US-Dollar" },
    { symbol: "GLD", name: "Gold" },
    { symbol: "USO", name: "Öl (WTI)" },
  ];
  
  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Block 9" cadence="60s Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Activity size={18} />
          Makro-Proxys
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
            {isStale(timestamp, 60) && (
              <span className="text-amber-500">⚠️ Stale</span>
            )}
          </div>
        )}
      </div>
      
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {proxies.map((proxy) => {
          const item = data.macro[proxy.symbol];
          if (!item || item.error) return null;
          
          return (
            <div key={proxy.symbol} className="p-3 rounded-lg bg-[var(--bg-tertiary)]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--text-muted)]">{proxy.name}</span>
                <TrendIcon value={item.change_1d_pct} />
              </div>
              <div className="text-lg font-bold text-[var(--text-primary)] mb-1">
                ${item.price?.toFixed(2) || "--"}
              </div>
              <div className={`text-sm font-medium ${
                item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"
              }`}>
                {formatPct(item.change_1d_pct)}
              </div>
              {item.rsi_14 && (
                <div className="mt-2">
                  <RSIBar value={item.rsi_14} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Loading Skeleton
function Skeleton() {
  return (
    <div className="animate-pulse space-y-6">
      {[...Array(9)].map((_, i) => (
        <div key={i} className="h-64 bg-[var(--bg-tertiary)] rounded-xl" />
      ))}
    </div>
  );
}

function FearGreedBlock({
  data,
  timestamp,
}: {
  data?: FearGreedData;
  timestamp?: string;
}) {
  if (!data) return <BlockError title="Fear & Greed" />;

  const score = data.score;

  // Farbe nach Score
  const color =
    score <= 25 ? "var(--accent-red)" :
    score <= 45 ? "#F97316" :         // orange
    score <= 55 ? "var(--accent-amber)" :
    score <= 75 ? "#84CC16" :         // lime
    "var(--accent-green)";

  // SVG Halbkreis-Gauge
  // Radius 70, stroke-dasharray für Halbkreis
  const r = 70;
  const circ = Math.PI * r;           // Halbkreis-Umfang
  const filled = (score / 100) * circ;

  return (
    <div className="card p-6">
      <BlockHeaderBadge block="Fear & Greed" cadence="30min Refresh" />
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold
                        text-[var(--text-primary)]
                        flex items-center gap-2">
          Fear & Greed Index
        </h3>
        {timestamp && (
          <div className="flex items-center gap-2
                           text-xs text-[var(--text-muted)]">
            <Clock size={12} />
            <span>{getTimeDelta(timestamp)}</span>
          </div>
        )}
      </div>

      {/* Gauge */}
      <div className="flex flex-col items-center mb-6">
        <svg
          viewBox="0 0 160 90"
          className="w-48 h-auto"
        >
          {/* Hintergrund-Halbkreis */}
          <path
            d="M 10 80 A 70 70 0 0 1 150 80"
            fill="none"
            stroke="var(--bg-tertiary)"
            strokeWidth="12"
            strokeLinecap="round"
          />
          {/* Füll-Halbkreis */}
          <path
            d="M 10 80 A 70 70 0 0 1 150 80"
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circ}`}
            style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
          />
          {/* Score Text */}
          <text
            x="80"
            y="72"
            textAnchor="middle"
            fontSize="24"
            fontWeight="700"
            fontFamily="DM Mono, monospace"
            fill="var(--text-primary)"
          >
            {Math.round(score)}
          </text>
        </svg>
        <p
          className="text-base font-bold mt-1"
          style={{ color }}
        >
          {data.label}
        </p>
      </div>

      {/* Komponenten */}
      <div className="space-y-2">
        {Object.entries(data.components).map(
          ([key, comp]) => (
            <div
              key={key}
              className="flex items-center gap-3"
            >
              <span className="text-[10px] w-32 shrink-0
                               text-[var(--text-muted)]
                               truncate">
                {comp.label}
              </span>
              {/* Mini-Balken */}
              <div className="flex-1 h-1.5 rounded-full
                               bg-[var(--bg-tertiary)]
                               overflow-hidden">
                <div
                  className="h-full rounded-full
                               transition-all duration-500"
                  style={{
                    width:      `${comp.score}%`,
                    background: comp.score >= 56
                      ? "var(--accent-green)"
                      : comp.score >= 46
                      ? "var(--accent-amber)"
                      : "var(--accent-red)",
                  }}
                />
              </div>
              <span className="text-xs font-mono w-8
                               text-right
                               text-[var(--text-secondary)]">
                {Math.round(comp.score)}
              </span>
            </div>
          )
        )}
      </div>
    </div>
  );
}

// Main Component
export default function MarketsPage() {
  // Block states with individual refresh intervals
  const [marketBreadth, setMarketBreadth] = useState<MarketBreadth | undefined>(undefined);
  const [macroDashboard, setMacroDashboard] = useState<MacroSnapshot | undefined>(undefined);
  const [crossAsset, setCrossAsset] = useState<IntermarketData | undefined>(undefined);
  const [newsSentiment, setNewsSentiment] = useState<NewsSentimentData | undefined>(undefined);
  const [economicCalendar, setEconomicCalendar] = useState<EconomicCalendar | undefined>(undefined);
  const [marketAudit, setMarketAudit] = useState<MarketAudit | undefined>(undefined);
  
  const [loading, setLoading] = useState(true);
  const [initialLoading, setInitialLoading] = useState(true);
  const [economicCalendarLoading, setEconomicCalendarLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [indexAnalysis, setIndexAnalysis] = useState<Record<string, any>>({});
  const [analysisPending, setAnalysisPending] = useState<Record<string, boolean>>({});

  const analyzeIndex = async (symbol: string) => {
    if (analysisPending[symbol] || indexAnalysis[symbol])
      return;
    setAnalysisPending(prev => ({ ...prev, [symbol]: true }));
    try {
      const res = await fetch(
        `/api/chart-analysis/${symbol}` 
      );
      const data = await res.json();
      setIndexAnalysis(prev => ({ ...prev, [symbol]: data }));
    } catch {
      setIndexAnalysis(prev => ({
        ...prev, [symbol]: { error: true }
      }));
    } finally {
      setAnalysisPending(prev =>
        ({ ...prev, [symbol]: false })
      );
    }
  };

  // Fetch functions for each block
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [marketOverviewTs, setMarketOverviewTs] = useState<string | undefined>();

  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);
  const [fearGreedTs, setFearGreedTs] = useState<string | undefined>();

  const fetchMarketOverview = useCallback(async () => {
    try {
      const data = await api.getMarketOverview();
      setMarketOverview(data);
      setMarketOverviewTs(data.timestamp);
    } catch (error) {
      console.error("Market Overview fetch error:", error);
    }
  }, []);

  const fetchFearGreed = useCallback(async () => {
    try {
      const data = await fetch("/api/data/fear-greed")
        .then(r => r.json());
      setFearGreed(data);
      setFearGreedTs(new Date().toISOString());
    } catch {}
  }, []);

  const fetchMarketBreadth = useCallback(async () => {
    try {
      const data = await api.getMarketBreadth();
      setMarketBreadth(data);
    } catch (error) {
      console.error("Market Breadth fetch error:", error);
      setMarketBreadth(undefined);
    }
  }, []);
  
  const fetchMacroDashboard = useCallback(async () => {
    try {
      const data = await api.getMacro();
      setMacroDashboard(data);
    } catch (error) {
      console.error("Macro Dashboard fetch error:", error);
      setMacroDashboard(undefined);
    }
  }, []);
  
  const fetchCrossAsset = useCallback(async () => {
    try {
      const data = await api.getIntermarket();
      setCrossAsset(data);
    } catch (error) {
      console.error("Cross Asset fetch error:", error);
      setCrossAsset(undefined);
    }
  }, []);
  
  const fetchNewsSentiment = useCallback(async () => {
    try {
      const data = await api.getMarketNewsSentiment();
      setNewsSentiment(data);
    } catch (error) {
      console.error("News Sentiment fetch error:", error);
      setNewsSentiment(undefined);
    }
  }, []);
  
  const fetchEconomicCalendar = useCallback(async () => {
    try {
      const data = await api.getEconomicCalendar();
      setEconomicCalendar(data);
    } catch (error) {
      console.error("Economic Calendar fetch error:", error);
      setEconomicCalendar(undefined);
    }
  }, []);

  const refreshEconomicCalendar = useCallback(async () => {
    setEconomicCalendarLoading(true);
    try {
      await api.runMacroScan();
      await fetchEconomicCalendar();
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Economic Calendar refresh error:", error);
    } finally {
      setEconomicCalendarLoading(false);
    }
  }, [fetchEconomicCalendar]);
  
  const generateAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const result = await api.generateMarketAudit();
      setMarketAudit(result);
    } catch (error) {
      console.error("Audit generation error:", error);
    } finally {
      setAuditLoading(false);
    }
  }, []);
  
  // Initial fetch with Promise.allSettled - Economic Calendar only on initial load
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetchMarketOverview(),
        fetchMarketBreadth(),
        fetchMacroDashboard(),
        fetchCrossAsset(),
        fetchNewsSentiment(),
        fetchEconomicCalendar(),
        fetchFearGreed(),
      ]);
      
      console.log("All blocks fetched:", results.map(r => r.status));
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Fetch all error:", error);
    } finally {
      setLoading(false);
      setInitialLoading(false);
    }
  }, [
    fetchMarketOverview,
    fetchMarketBreadth,
    fetchMacroDashboard,
    fetchCrossAsset,
    fetchNewsSentiment,
    fetchEconomicCalendar,
  ]);

  const sharedMarketOverview = marketOverview ?? undefined;
  const sharedMarketOverviewTs = marketOverview?.timestamp ?? marketOverviewTs;
  
  // Set up individual refresh intervals
  useEffect(() => {
    fetchAll();
    
    // 60s: Market Overview (covers Global Indices, Sector Rotation, Macro Proxies)
    const interval60 = setInterval(() => {
      fetchMarketOverview();
    }, 60000);
    
    // 5min: Market Breadth
    const interval300 = setInterval(fetchMarketBreadth, 300000);
    
    // 30min: Macro Dashboard + Fear & Greed only (Economic Calendar now manual)
    const interval1800 = setInterval(() => {
      Promise.allSettled([
        fetchMacroDashboard(),
        fetchFearGreed(),
      ]);
    }, 1800000);
    
    // 10min: Cross Asset, News Sentiment
    const interval600 = setInterval(() => {
      Promise.allSettled([
        fetchCrossAsset(),
        fetchNewsSentiment(),
      ]);
    }, 600000);
    
    return () => {
      clearInterval(interval60);
      clearInterval(interval300);
      clearInterval(interval1800);
      clearInterval(interval600);
    };
  }, [
    fetchAll,
    fetchMarketOverview,
    fetchMarketBreadth,
    fetchMacroDashboard,
    fetchCrossAsset,
    fetchNewsSentiment,
  ]);
  
  if (loading) {
    return (
      <div className="p-8">
        <h1 className="text-4xl font-bold text-[var(--text-primary)] mb-8">Markets Dashboard v2</h1>
        <Skeleton />
      </div>
    );
  }
  
  return (
    <div className="space-y-6 p-8">
      {/* Initial Loading Banner */}
      {initialLoading && (
        <div className="flex items-center gap-3
                         rounded-xl bg-[var(--bg-tertiary)]
                         border border-[var(--border)]
                         px-4 py-3 mb-4">
          <div className="h-2 w-2 rounded-full
                           bg-[var(--accent-blue)]
                           animate-pulse" />
          <p className="text-xs text-[var(--text-secondary)]">
            Marktdaten werden geladen
            {/* Dot-Animation */}
            <span className="animate-pulse">…</span>
          </p>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Markets Dashboard v2</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2">
            Granulare Echtzeit-Marktanalyse mit individuellen Refresh-Zyklen
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end text-xs text-[var(--text-secondary)]">
            {lastUpdate && (
              <span>Zuletzt aktualisiert: {lastUpdate.toLocaleTimeString("de-DE")}</span>
            )}
          </div>
          <Link
            href="/markets/info"
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            title="Dashboard-Info öffnen"
          >
            <Info size={16} />
            <span className="hidden sm:inline">Info</span>
          </Link>
          <button
            onClick={fetchAll}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            {loading ? "Lädt..." : "Alle aktualisieren"}
          </button>
        </div>
      </div>

      {/* Composite Regime Header */}
      <RegimeHeader data={{
        vix: macroDashboard?.vix,
        creditSpread: macroDashboard?.credit_spread_bps,
        yieldSpread: macroDashboard?.yield_curve_10y_2y,
        breadthPct: marketBreadth?.pct_above_sma50,
        riskAppetite: crossAsset?.signals?.risk_appetite,
        vixStructure: crossAsset?.signals?.vix_structure,
      }} />
      
      {/* 9 Data Blocks Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Block 1: Global Indices */}
        <GlobalIndicesBlock 
          data={sharedMarketOverview} 
          timestamp={sharedMarketOverviewTs} 
          indexAnalysis={indexAnalysis}
          analysisPending={analysisPending}
          onAnalyze={analyzeIndex}
          onRemoveAnalysis={(symbol) => {
            setIndexAnalysis(prev => {
              const next = { ...prev };
              delete next[symbol];
              return next;
            });
          }}
        />
        
        {/* Block 2: Sector Rotation */}
        <SectorRotationBlock 
          data={sharedMarketOverview} 
          timestamp={sharedMarketOverviewTs} 
        />
        
        {/* Block 3: Market Breadth */}
        <MarketBreadthBlock 
          data={marketBreadth} 
          timestamp={marketBreadth ? new Date().toISOString() : undefined} 
        />
        
        {/* Block 4: Macro Dashboard */}
        <MacroDashboardBlock 
          data={macroDashboard} 
          timestamp={macroDashboard ? new Date().toISOString() : undefined} 
        />
        <VIXDetailBlock intermarket={crossAsset} macro={macroDashboard} />
        
        {/* Fear & Greed Block */}
        <FearGreedBlock
          data={fearGreed ?? undefined}
          timestamp={fearGreedTs}
        />
        
        {/* Block 5: Cross-Asset Signals */}
        <CrossAssetBlock 
          data={crossAsset} 
          timestamp={crossAsset ? new Date().toISOString() : undefined} 
        />
        
        {/* Block 6: Market News + FinBERT Sentiment */}
        <NewsSentimentBlock 
          data={newsSentiment} 
          timestamp={newsSentiment?.fetched_at} 
        />
        
        {/* Block 7: Economic Calendar */}
        <EconomicCalendarBlock 
          data={economicCalendar} 
          timestamp={economicCalendar ? new Date().toISOString() : undefined}
          onRefresh={refreshEconomicCalendar}
          loading={economicCalendarLoading}
        />
        
        {/* Block 8: Market Audit */}
        <MarketAuditBlock 
          audit={marketAudit || undefined} 
          onGenerate={generateAudit} 
          loading={auditLoading} 
        />
        
        {/* Block 9: Macro Proxies */}
        <MacroProxiesBlock 
          data={sharedMarketOverview} 
          timestamp={sharedMarketOverviewTs} 
        />
      </div>
    </div>
  );
}
