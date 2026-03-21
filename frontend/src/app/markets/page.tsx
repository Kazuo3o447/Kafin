"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { cacheGet, cacheSet } from "@/lib/clientCache";
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
  Clock
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

type NewsItem = {
  headline: string;
  summary?: string;
  source: string;
  url?: string;
  datetime: number;
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

function RSIBar({ value }: { value?: number }) {
  if (!value) return <span className="text-muted">—</span>;
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

// Regime Ampel Component
function RegimeAmpel({ macro, breadth }: { macro: MacroSnapshot; breadth?: MarketBreadth }) {
  const regime = macro.regime?.toUpperCase() || "MIXED";
  const isRiskOn = regime.includes("ON");
  const isRiskOff = regime.includes("OFF");

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-6">
          <div 
            className={`flex h-16 w-16 items-center justify-center rounded-2xl ${
              isRiskOn ? "bg-green-500/20" : isRiskOff ? "bg-red-500/20" : "bg-amber-500/20"
            }`}
          >
            <Activity size={32} className={
              isRiskOn ? "text-green-500" : isRiskOff ? "text-red-500" : "text-amber-500"
            } />
          </div>
          <div>
            <p className="text-sm text-[var(--text-secondary)] mb-1">Marktregime</p>
            <h2 className="text-3xl font-bold text-[var(--text-primary)]">
              {isRiskOn ? "🟢 RISK-ON" : isRiskOff ? "🔴 RISK-OFF" : "🟡 MIXED"}
            </h2>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3">
          {macro.vix !== undefined && (
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              macro.vix > 25 ? "bg-red-500/20 text-red-300" : 
              macro.vix > 15 ? "bg-amber-500/20 text-amber-300" : 
              "bg-green-500/20 text-green-300"
            }`}>
              VIX: {macro.vix.toFixed(1)}
            </span>
          )}
          {macro.credit_spread_bps !== undefined && (
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              macro.credit_spread_bps > 500 ? "bg-red-500/20 text-red-300" : 
              macro.credit_spread_bps > 350 ? "bg-amber-500/20 text-amber-300" : 
              "bg-green-500/20 text-green-300"
            }`}>
              Credit: {macro.credit_spread_bps.toFixed(0)}bp
            </span>
          )}
          {macro.yield_curve_10y_2y !== undefined && (
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              macro.yield_curve_10y_2y < -0.1 ? "bg-red-500/20 text-red-300" : 
              macro.yield_curve_10y_2y < 0.1 ? "bg-amber-500/20 text-amber-300" : 
              "bg-green-500/20 text-green-300"
            }`}>
              Curve: {macro.yield_curve_10y_2y.toFixed(2)}%
            </span>
          )}
          {breadth?.breadth_signal && (
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              breadth.breadth_signal === "stark" ? "bg-green-500/20 text-green-300" : 
              breadth.breadth_signal === "schwach" ? "bg-red-500/20 text-red-300" : 
              "bg-amber-500/20 text-amber-300"
            }`}>
              Breadth: {breadth.breadth_signal.toUpperCase()}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// Index Cards Component
function IndexCards({ data }: { data: Record<string, IndexData> }) {
  const indices = ["SPY", "QQQ", "DIA", "^GDAXI", "URTH", "IWM"];
  
  return (
    <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
      {indices.map((symbol) => {
        const item = data[symbol];
        if (!item || item.error) return null;
        
        return (
          <div key={symbol} className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-[var(--text-muted)]">{item.name}</span>
              <TrendIcon value={item.change_1d_pct} />
            </div>
            <div className="text-xl font-bold text-[var(--text-primary)] mb-1">
              ${item.price?.toFixed(2) || "--"}
            </div>
            <div className={`text-sm mb-2 ${item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
              {formatPct(item.change_1d_pct)}
            </div>
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span>RSI</span>
              <RSIBar value={item.rsi_14} />
            </div>
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)] mt-1">
              <span>SMA50</span>
              <span>{item.above_sma50 ? "✓" : "✗"}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)] mt-1">
              <span>Trend</span>
              <span className="capitalize">{item.trend || "-"}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Market Breadth Component
function MarketBreadthBlock({ data }: { data?: MarketBreadth }) {
  if (!data || data.error) return null;
  
  const getColor = (val: number) => {
    if (val >= 70) return "var(--accent-green)";
    if (val >= 40) return "var(--accent-amber)";
    return "var(--accent-red)";
  };

  return (
    <div className="card p-6">
      <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <BarChart3 size={18} />
        Marktbreite
      </h3>
      <div className="grid grid-cols-2 gap-6">
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
      <div className="mt-4 pt-4 border-t border-[var(--border)]">
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--text-muted)]">Advancing</span>
          <span className="text-[var(--accent-green)] font-medium">{data.advancing}</span>
        </div>
        <div className="flex items-center justify-between text-sm mt-1">
          <span className="text-[var(--text-muted)]">Declining</span>
          <span className="text-[var(--accent-red)] font-medium">{data.declining}</span>
        </div>
        <div className="mt-3 text-xs text-[var(--text-muted)]">
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

// Sector Heatmap Component
function SectorHeatmap({ sectors }: { sectors: Array<{ symbol: string; name: string; perf_5d: number }> }) {
  if (!sectors.length) return null;

  const top3 = sectors.slice(0, 3);
  const bottom3 = sectors.slice(-3).reverse();

  return (
    <div className="card p-6">
      <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <Globe size={18} />
        Sektor-Rotation
      </h3>
      <div className="grid grid-cols-3 md:grid-cols-4 gap-2">
        {sectors.map((sector) => (
          <div 
            key={sector.symbol}
            className={`p-3 rounded-xl text-center ${getSectorColor(sector.perf_5d)}`}
          >
            <div className="text-xs font-bold">{sector.symbol}</div>
            <div className="text-xs mt-1">{sector.perf_5d.toFixed(1)}%</div>
            <div className="text-[10px] opacity-70 mt-1 truncate">{sector.name}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-[var(--text-secondary)]">
        <span className="text-[var(--accent-green)]">Stärkste: {top3.map(s => s.symbol).join(", ")}</span>
        <span className="mx-2">|</span>
        <span className="text-[var(--accent-red)]">Schwächste: {bottom3.map(s => s.symbol).join(", ")}</span>
      </div>
    </div>
  );
}

// Cross-Asset Signals Component
function CrossAssetSignals({ data }: { data?: IntermarketData }) {
  if (!data?.assets) return null;

  const { assets, signals } = data;
  const displayAssets = ["GLD", "USO", "UUP", "TLT", "EEM", "HYG"];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="card p-6">
        <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Cross-Asset</h3>
        <div className="space-y-3">
          {displayAssets.map((symbol) => {
            const asset = assets[symbol];
            if (!asset) return null;
            return (
              <div key={symbol} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <TrendIcon value={asset.change_1d} />
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{asset.name}</p>
                    <p className="text-xs text-[var(--text-muted)]">${asset.price.toFixed(2)}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-medium ${asset.change_1d >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                    {formatPct(asset.change_1d)}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">1M: {formatPct(asset.change_1m)}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Signale</h3>
        <div className="space-y-4">
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
                <span className="font-semibold text-[var(--text-primary)]">
                  Risk Appetite: {signals.risk_appetite.replace("_", "-").toUpperCase()}
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
                <span className="font-semibold text-[var(--text-primary)]">
                  VIX: {signals.vix_structure.toUpperCase()}
                </span>
              </div>
              {signals.vix_note && (
                <p className="text-xs text-[var(--text-muted)] mt-1">{signals.vix_note}</p>
              )}
            </div>
          )}
          {signals.credit_signal && (
            <div className={`p-3 rounded-lg ${
              signals.credit_signal === "warnung" ? "bg-red-500/10 border border-red-500/30" :
              signals.credit_signal === "gesund" ? "bg-green-500/10 border border-green-500/30" :
              "bg-[var(--bg-tertiary)]"
            }`}>
              <div className="flex items-center gap-2">
                {signals.credit_signal === "warnung" ? <AlertTriangle size={16} className="text-red-500" /> :
                 signals.credit_signal === "gesund" ? <CheckCircle2 size={16} className="text-green-500" /> :
                 <Minus size={16} className="text-[var(--text-muted)]" />}
                <span className="font-semibold text-[var(--text-primary)]">
                  Credit: {signals.credit_signal.toUpperCase()}
                </span>
              </div>
              {signals.credit_note && (
                <p className="text-xs text-[var(--text-muted)] mt-1">{signals.credit_note}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Macro Dashboard Component
function MacroDashboard({ macro }: { macro: MacroSnapshot }) {
  const cards = [
    { 
      label: "Fed Rate", 
      value: macro.fed_rate !== undefined ? `${macro.fed_rate.toFixed(2)}%` : "--",
      note: "Aktuelle Leitzins"
    },
    { 
      label: "VIX", 
      value: macro.vix !== undefined ? macro.vix.toFixed(2) : "--",
      note: macro.vix && macro.vix > 25 ? "Stress" : macro.vix && macro.vix > 15 ? "Normal" : "Euphorie",
      color: macro.vix && macro.vix > 25 ? "text-red-400" : macro.vix && macro.vix > 15 ? "text-amber-400" : "text-green-400"
    },
    { 
      label: "Credit Spread", 
      value: macro.credit_spread_bps !== undefined ? `${macro.credit_spread_bps.toFixed(0)}bp` : "--",
      note: macro.credit_spread_bps && macro.credit_spread_bps > 500 ? "Stress" : 
            macro.credit_spread_bps && macro.credit_spread_bps > 350 ? "Erhöht" : "Gesund",
      color: macro.credit_spread_bps && macro.credit_spread_bps > 500 ? "text-red-400" : 
            macro.credit_spread_bps && macro.credit_spread_bps > 350 ? "text-amber-400" : "text-green-400"
    },
    { 
      label: "Yield Curve", 
      value: macro.yield_curve_10y_2y !== undefined ? `${macro.yield_curve_10y_2y.toFixed(2)}%` : "--",
      note: macro.yield_curve === "inverted" ? "Rezessionsrisiko" : 
            macro.yield_curve === "flat" ? "Warnung" : "Normal",
      color: macro.yield_curve === "inverted" ? "text-red-400" : 
            macro.yield_curve === "flat" ? "text-amber-400" : "text-green-400"
    },
  ];

  return (
    <div className="card p-6">
      <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <Activity size={18} />
        Makro-Dashboard
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="p-4 rounded-xl bg-[var(--bg-tertiary)]">
            <p className="text-xs text-[var(--text-muted)] mb-1">{card.label}</p>
            <p className={`text-xl font-bold ${card.color || "text-[var(--text-primary)]"}`}>
              {card.value}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{card.note}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// News Component
function NewsSection({ news }: { news: NewsItem[] }) {
  if (!news.length) return null;

  return (
    <div className="card p-6">
      <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <Newspaper size={18} />
        Marktnachrichten
      </h3>
      <div className="space-y-3 max-h-80 overflow-y-auto">
        {news.slice(0, 8).map((item, idx) => {
          const date = new Date(item.datetime * 1000);
          return (
            <a 
              key={idx} 
              href={item.url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="block p-3 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)] transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-medium text-[var(--text-primary)] line-clamp-2">{item.headline}</h4>
              </div>
              <div className="flex items-center gap-2 mt-2 text-xs text-[var(--text-muted)]">
                <span>{item.source}</span>
                <span>•</span>
                <span>{date.toLocaleDateString("de-DE")}</span>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

// Market Audit Component
function MarketAuditSection({ audit, onGenerate, loading }: { 
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

// Loading Skeleton
function Skeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-24 bg-[var(--bg-tertiary)] rounded-xl mb-6" />
      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6 mb-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-32 bg-[var(--bg-tertiary)] rounded-xl" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2 mb-6">
        <div className="h-64 bg-[var(--bg-tertiary)] rounded-xl" />
        <div className="h-64 bg-[var(--bg-tertiary)] rounded-xl" />
      </div>
    </div>
  );
}

// Main Component
export default function MarketsPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [breadth, setBreadth] = useState<MarketBreadth | null>(null);
  const [intermarket, setIntermarket] = useState<IntermarketData | null>(null);
  const [macro, setMacro] = useState<MacroSnapshot | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [audit, setAudit] = useState<MarketAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewData, breadthData, intermarketData, macroData] = await Promise.all([
        api.getMarketOverview(),
        api.getMarketBreadth(),
        api.getIntermarket(),
        api.getMacro(),
      ]);

      setOverview(overviewData);
      setBreadth(breadthData);
      setIntermarket(intermarketData);
      setMacro(macroData);
      setLastUpdate(new Date());

      // Fetch news separately (may fail)
      try {
        const newsData = await fetch("/api/news/general").then(r => r.ok ? r.json() : []);
        setNews(newsData || []);
      } catch {
        setNews([]);
      }
    } catch (error) {
      console.error("Markets fetch error:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  const generateAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const result = await api.generateMarketAudit();
      setAudit(result);
    } catch (error) {
      console.error("Audit generation error:", error);
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading || !overview || !macro) {
    return (
      <div className="p-8">
        <h1 className="text-4xl font-bold text-[var(--text-primary)] mb-8">Markets</h1>
        <Skeleton />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Markets</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2">
            Trading-grade Marktanalyse & Regime-Erkennung
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end text-xs text-[var(--text-secondary)]">
            {lastUpdate && (
              <span>Zuletzt aktualisiert: {lastUpdate.toLocaleTimeString("de-DE")}</span>
            )}
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            {loading ? "Lädt..." : "Aktualisieren"}
          </button>
        </div>
      </div>

      {/* Regime Ampel */}
      <RegimeAmpel macro={macro} breadth={breadth || undefined} />

      {/* Index Cards */}
      <IndexCards data={overview.indices} />

      {/* Market Breadth & Sector Heatmap */}
      <div className="grid gap-6 lg:grid-cols-2">
        <MarketBreadthBlock data={breadth || undefined} />
        <SectorHeatmap sectors={overview.sector_ranking_5d || []} />
      </div>

      {/* Cross-Asset Signals */}
      <CrossAssetSignals data={intermarket || undefined} />

      {/* Macro Dashboard */}
      <MacroDashboard macro={macro} />

      {/* News & Market Audit */}
      <div className="grid gap-6 lg:grid-cols-2">
        <NewsSection news={news} />
        <MarketAuditSection 
          audit={audit || undefined} 
          onGenerate={generateAudit} 
          loading={auditLoading} 
        />
      </div>
    </div>
  );
}
