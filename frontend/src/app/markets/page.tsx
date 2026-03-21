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
} from "lucide-react";

// Types
type IndexData = {
  name: string;
  price?: number;
  change_1d_pct?: number;
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
  signals: Record<string, string>;
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
};

type NewsSentimentData = {
  headlines: NewsSentimentItem[];
  category_sentiment: Record<string, { score: number; count: number; label: string }>;
  total_analyzed: number;
  fetched_at: string;
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

// Block 1: Global Indices
function GlobalIndicesBlock({ data, timestamp }: { data?: MarketOverview; timestamp?: string }) {
  if (!data?.indices) return <BlockError title="Globale Indizes" />;
  
  const indices = [
    "SPY", "QQQ", "DIA", "IWM", "^GDAXI", "^STOXX50E", "^N225", "URTH"
  ];
  
  return (
    <div className="card p-6">
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
              <div className="text-xs text-[var(--text-muted)] mt-1">
                {item.name}
              </div>
            </div>
          );
        })}
      </div>
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
            <div className="text-xs font-bold">{sector.symbol}</div>
            <div className="text-xs mt-1">{sector.perf_5d.toFixed(1)}%</div>
          </div>
        ))}
      </div>
      
      <div className="text-xs text-[var(--text-secondary)]">
        <span className="text-[var(--accent-green)]">Top: {top3.map(s => s.symbol).join(", ")}</span>
        <span className="mx-2">|</span>
        <span className="text-[var(--accent-red)]">Bottom: {bottom3.map(s => s.symbol).join(", ")}</span>
      </div>
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
            <span className="font-semibold text-[var(--text-primary)]">
              Regime: {data.regime.toUpperCase()}
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
          <div className="space-y-2">
            {displayAssets.map((symbol) => {
              const asset = assets[symbol];
              if (!asset) return null;
              return (
                <div key={symbol} className="flex items-center justify-between p-2 rounded bg-[var(--bg-tertiary)]">
                  <div className="flex items-center gap-2">
                    <TrendIcon value={asset.change_1d} />
                    <span className="text-sm font-medium">{symbol}</span>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-medium ${
                      asset.change_1d >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"
                    }`}>
                      {formatPct(asset.change_1d)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
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
          </div>
        </div>
      </div>
    </div>
  );
}

// Block 6: Market News + FinBERT Sentiment
function NewsSentimentBlock({ data, timestamp }: { data?: NewsSentimentData; timestamp?: string }) {
  if (!data?.headlines) return <BlockError title="Marktnachrichten + Sentiment" />;
  
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
  
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Newspaper size={18} />
          Marktnachrichten + FinBERT
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
      
      {/* Category Sentiment Summary */}
      {Object.keys(data.category_sentiment).length > 0 && (
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
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {data.headlines.slice(0, 10).map((item, idx) => (
          <div key={idx} className="p-3 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)] transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <h4 className="text-sm font-medium text-[var(--text-primary)] line-clamp-2 mb-1">
                  {item.headline}
                </h4>
                <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  <span>{item.source}</span>
                  <span>•</span>
                  <span className="capitalize">{item.category.replace('_', ' ')}</span>
                </div>
              </div>
              <div className="text-right">
                <div className={`text-xs font-bold ${getSentimentColor(item.sentiment_score)}`}>
                  {getSentimentLabel(item.sentiment_score)}
                </div>
                <div className="text-xs text-[var(--text-muted)]">
                  {item.sentiment_score.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 text-xs text-[var(--text-muted)] text-center">
        {data.total_analyzed} Headlines analysiert
      </div>
    </div>
  );
}

// Block 7: Economic Calendar
function EconomicCalendarBlock({ data, timestamp }: { data?: EconomicCalendar; timestamp?: string }) {
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
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Timer size={18} />
          Wirtschaftskalender (48h)
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

// Main Component
export default function MarketsPage() {
  // Block states with individual refresh intervals
  const [globalIndices, setGlobalIndices] = useState<MarketOverview | undefined>(undefined);
  const [sectorRotation, setSectorRotation] = useState<MarketOverview | undefined>(undefined);
  const [marketBreadth, setMarketBreadth] = useState<MarketBreadth | undefined>(undefined);
  const [macroDashboard, setMacroDashboard] = useState<MacroSnapshot | undefined>(undefined);
  const [crossAsset, setCrossAsset] = useState<IntermarketData | undefined>(undefined);
  const [newsSentiment, setNewsSentiment] = useState<NewsSentimentData | undefined>(undefined);
  const [economicCalendar, setEconomicCalendar] = useState<EconomicCalendar | undefined>(undefined);
  const [marketAudit, setMarketAudit] = useState<MarketAudit | undefined>(undefined);
  const [macroProxies, setMacroProxies] = useState<MarketOverview | undefined>(undefined);
  
  const [loading, setLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  
  // Fetch functions for each block
  const fetchGlobalIndices = useCallback(async () => {
    try {
      const data = await api.getMarketOverview();
      setGlobalIndices(data);
    } catch (error) {
      console.error("Global Indices fetch error:", error);
      setGlobalIndices(undefined);
    }
  }, []);
  
  const fetchSectorRotation = useCallback(async () => {
    try {
      const data = await api.getMarketOverview();
      setSectorRotation(data);
    } catch (error) {
      console.error("Sector Rotation fetch error:", error);
      setSectorRotation(undefined);
    }
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
  
  const fetchMacroProxies = useCallback(async () => {
    try {
      const data = await api.getMarketOverview();
      setMacroProxies(data);
    } catch (error) {
      console.error("Macro Proxies fetch error:", error);
      setMacroProxies(undefined);
    }
  }, []);
  
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
  
  // Initial fetch with Promise.allSettled
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetchGlobalIndices(),
        fetchSectorRotation(),
        fetchMarketBreadth(),
        fetchMacroDashboard(),
        fetchCrossAsset(),
        fetchNewsSentiment(),
        fetchEconomicCalendar(),
        fetchMacroProxies(),
      ]);
      
      console.log("All blocks fetched:", results.map(r => r.status));
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Fetch all error:", error);
    } finally {
      setLoading(false);
    }
  }, [
    fetchGlobalIndices,
    fetchSectorRotation,
    fetchMarketBreadth,
    fetchMacroDashboard,
    fetchCrossAsset,
    fetchNewsSentiment,
    fetchEconomicCalendar,
    fetchMacroProxies,
  ]);
  
  // Set up individual refresh intervals
  useEffect(() => {
    fetchAll();
    
    // 60s: Global Indices, Sector Rotation, Macro Proxies
    const interval60 = setInterval(() => {
      Promise.allSettled([
        fetchGlobalIndices(),
        fetchSectorRotation(),
        fetchMacroProxies(),
      ]);
    }, 60000);
    
    // 5min: Market Breadth
    const interval300 = setInterval(fetchMarketBreadth, 300000);
    
    // 30min: Macro Dashboard, Economic Calendar
    const interval1800 = setInterval(() => {
      Promise.allSettled([
        fetchMacroDashboard(),
        fetchEconomicCalendar(),
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
    fetchGlobalIndices,
    fetchSectorRotation,
    fetchMacroProxies,
    fetchMarketBreadth,
    fetchMacroDashboard,
    fetchEconomicCalendar,
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
      
      {/* 9 Blocks Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Block 1: Global Indices */}
        <GlobalIndicesBlock 
          data={globalIndices} 
          timestamp={globalIndices?.timestamp} 
        />
        
        {/* Block 2: Sector Rotation */}
        <SectorRotationBlock 
          data={sectorRotation} 
          timestamp={sectorRotation?.timestamp} 
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
        />
        
        {/* Block 8: Market Audit */}
        <MarketAuditBlock 
          audit={marketAudit || undefined} 
          onGenerate={generateAudit} 
          loading={auditLoading} 
        />
        
        {/* Block 9: Macro Proxies */}
        <MacroProxiesBlock 
          data={macroProxies} 
          timestamp={macroProxies?.timestamp} 
        />
      </div>
    </div>
  );
}
