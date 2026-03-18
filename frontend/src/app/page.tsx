"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown, Activity, DollarSign, Percent, Circle, RefreshCw, ArrowDownRight, ArrowUpRight, Info, Calendar as CalendarIcon, Clock } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import { cachedFetch, cacheAge, cacheInvalidateAll } from "@/lib/clientCache";
import { CacheStatus } from "@/components/CacheStatus";

type IndexData = {
  name: string;
  price?: number;
  change_1d_pct?: number;
  rsi_14?: number;
  trend?: string;
  error?: string;
};

type SectorRank = { symbol: string; name: string; perf_5d: number };

type MacroSnapshot = {
  regime?: string;
  fed_rate?: number;
  vix?: number;
  credit_spread_bps?: number;
  yield_curve_10y_2y?: number;
  dxy?: number;
};

type WatchlistItem = {
  ticker: string;
  company_name?: string;
  sector?: string;
  notes?: string;
  opportunity_score?: number;
  torpedo_score?: number;
  opp_delta?: number;
  torp_delta?: number;
  price?: number;
  change_pct?: number;
  rsi?: number;
  trend?: string;
  earnings_date?: string;
  earnings_countdown?: number;
};

type SparklinePoint = { date: string; price: number };

type WatchlistResponse = {
  watchlist: WatchlistItem[];
  concentration_warning?: string | null;
  sector_distribution?: Record<string, number>;
};

type OpportunityItem = {
  ticker: string;
  name: string;
  sector?: string;
  market_cap_b?: number;
  price?: number;
  rsi?: number;
  volatility?: number;
  interest_score?: number;
  earnings_date?: string;
  analysis?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(endpoint: string, revalidate = 60): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function getDashboardData(invalidate = false) {
  if (invalidate) cacheInvalidateAll();

  try {
    const [
      { data: macro, fromCache: macroFromCache },
      { data: overview },
      { data: report },
      { data: watchlistResp },
      { data: opportunitiesResp }
    ] = await Promise.all([
      cachedFetch("dashboard:macro", () => fetchJSON<MacroSnapshot>("/api/data/macro"), 120),
      cachedFetch("dashboard:overview", () => fetchJSON<{ indices: Record<string, IndexData>; sector_ranking_5d: SectorRank[]; macro: Record<string, IndexData> }>("/api/data/market-overview"), 120),
      cachedFetch("dashboard:report", () => fetchJSON<{ report?: string }>("/api/reports/latest").catch(() => ({ report: "" })), 60),
      cachedFetch("dashboard:watchlist", () => fetchJSON<WatchlistResponse>("/api/watchlist/enriched").catch(() => ({ watchlist: [], concentration_warning: null, sector_distribution: {} })), 60),
      cachedFetch("dashboard:opportunities", () => fetchJSON<{ opportunities?: OpportunityItem[] }>("/api/opportunities").catch(() => ({ opportunities: [] })), 120),
    ]);

    return {
      macro,
      overview,
      report: report.report || "Noch kein Briefing.",
      watchlist: watchlistResp.watchlist || [],
      concentrationWarning: watchlistResp.concentration_warning,
      sectorDistribution: watchlistResp.sector_distribution || {},
      opportunities: opportunitiesResp.opportunities || [],
      macroFromCache,
    };
  } catch (error) {
    console.error("Dashboard fetch error", error);
    return {
      macro: {},
      overview: { indices: {}, sector_ranking_5d: [], macro: {} },
      report: "API nicht erreichbar.",
      watchlist: [] as WatchlistItem[],
      concentrationWarning: null,
      sectorDistribution: {},
      opportunities: [] as OpportunityItem[],
      macroFromCache: false,
    };
  }
}

function TrendIcon({ value }: { value?: number }) {
  if (value === undefined || value === null) return <Info size={14} className="text-[var(--text-muted)]" />;
  return value >= 0 ? (
    <ArrowUpRight size={16} className="text-[var(--accent-green)]" />
  ) : (
    <ArrowDownRight size={16} className="text-[var(--accent-red)]" />
  );
}

function formatPct(value?: number, fallback = "--") {
  if (value === undefined || value === null || Number.isNaN(value)) return fallback;
  const formatted = value.toFixed(2).replace("-0.00", "0.00");
  return `${formatted}%`;
}

function MacroBanner({ macro }: { macro: MacroSnapshot }) {
  const regime = macro.regime?.toUpperCase() || "CAUTIOUS";
  const isRiskOn = regime.includes("RISK") && regime.includes("ON");
  const isRiskOff = regime.includes("RISK") && regime.includes("OFF");

  return (
    <div className="card p-8">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-6">
          <div className={`flex h-16 w-16 items-center justify-center rounded-2xl ${
            isRiskOn ? "bg-[var(--accent-green)] bg-opacity-10" : isRiskOff ? "bg-[var(--accent-red)] bg-opacity-10" : "bg-[var(--accent-amber)] bg-opacity-10"
          }`}>
            <Circle size={32} className={`${
              isRiskOn ? "fill-[var(--accent-green)] text-[var(--accent-green)]" : isRiskOff ? "fill-[var(--accent-red)] text-[var(--accent-red)]" : "fill-[var(--accent-amber)] text-[var(--accent-amber)]"
            }`} />
          </div>
          <div>
            <p className="text-sm text-[var(--text-secondary)] mb-1">Market Regime</p>
            <h2 className="text-3xl font-bold text-[var(--text-primary)]">{regime}</h2>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-6 md:grid-cols-5">
          {[
            { label: "Fed Rate", value: macro.fed_rate ? `${macro.fed_rate.toFixed(2)}%` : "-", color: "text-[var(--text-primary)]" },
            { label: "VIX", value: macro.vix ? macro.vix.toFixed(2) : "-", color: macro.vix && macro.vix > 25 ? "text-[var(--accent-red)]" : "text-[var(--accent-green)]" },
            { label: "Credit Spread", value: macro.credit_spread_bps ? `${macro.credit_spread_bps.toFixed(0)} bp` : "-", color: "text-[var(--text-primary)]" },
            { label: "Yield Curve", value: macro.yield_curve_10y_2y ? `${macro.yield_curve_10y_2y.toFixed(2)}%` : "-", color: macro.yield_curve_10y_2y && macro.yield_curve_10y_2y < 0 ? "text-[var(--accent-red)]" : "text-[var(--text-primary)]" },
            { label: "DXY", value: macro.dxy ? macro.dxy.toFixed(2) : "-", color: "text-[var(--text-primary)]" },
          ].map((item) => (
            <div key={item.label}>
              <p className="text-xs text-[var(--text-muted)] mb-1">{item.label}</p>
              <p className={`text-xl font-bold ${item.color}`}>{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IndexCards({ data }: { data: Record<string, IndexData> }) {
  const entries = Object.entries(data);
  if (!entries.length) return null;
  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
      {entries.map(([symbol, item]) => (
        <div key={symbol} className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-xs text-[var(--text-muted)] mb-1">{item.name}</p>
              <h3 className="text-xl font-bold text-[var(--text-primary)]">{symbol}</h3>
            </div>
            <TrendIcon value={item.change_1d_pct} />
          </div>
          <div className="flex items-end justify-between">
            <div>
              <p className="text-3xl font-bold text-[var(--text-primary)]">${item.price?.toFixed(2) || "--"}</p>
              <p className={`text-sm font-medium mt-1 ${item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                {formatPct(item.change_1d_pct)} today
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-[var(--text-muted)] mb-1">RSI</p>
              <p className="text-sm font-semibold text-[var(--text-primary)]">{item.rsi_14 ? item.rsi_14.toFixed(1) : "--"}</p>
              <p className="text-xs text-[var(--text-muted)] capitalize mt-1">{item.trend || "-"}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SectorTable({ sectors }: { sectors: SectorRank[] }) {
  if (!sectors.length) return null;
  const top = sectors.slice(0, 5);
  const bottom = sectors.slice(-5).reverse();
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="card p-6">
        <h4 className="text-lg font-bold text-[var(--text-primary)] mb-4">Top Performers</h4>
        <div className="space-y-4">
          {top.map((item) => (
            <div key={item.symbol}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-[var(--text-primary)]">{item.name}</span>
                <span className="text-sm font-bold text-[var(--accent-green)]">{formatPct(item.perf_5d)}</span>
              </div>
              <div className="h-2 w-full rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--accent-green)]"
                  style={{ width: `${Math.min(100, Math.abs(item.perf_5d) * 10)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="card p-6">
        <h4 className="text-lg font-bold text-[var(--text-primary)] mb-4">Worst Performers</h4>
        <div className="space-y-4">
          {bottom.map((item) => (
            <div key={item.symbol}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-[var(--text-primary)]">{item.name}</span>
                <span className="text-sm font-bold text-[var(--accent-red)]">{formatPct(item.perf_5d)}</span>
              </div>
              <div className="h-2 w-full rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--accent-red)]"
                  style={{ width: `${Math.min(100, Math.abs(item.perf_5d) * 10)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MacroProxies({ macro }: { macro: Record<string, IndexData> }) {
  if (!Object.keys(macro).length) return null;
  return (
    <div className="card p-6">
      <h4 className="text-lg font-bold text-[var(--text-primary)] mb-4">Macro Proxies</h4>
      <div className="space-y-4">
        {Object.entries(macro).map(([symbol, item]) => (
          <div key={symbol} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <TrendIcon value={item.change_1d_pct} />
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)]">{item.name}</p>
                <p className="text-xs text-[var(--text-muted)]">{symbol}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-[var(--text-primary)]">${item.price?.toFixed(2) || "--"}</p>
              <p className={`text-sm font-medium ${item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                {formatPct(item.change_1d_pct)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BriefingPreview({ report }: { report: string }) {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-[var(--text-primary)]">Morning Briefing</h3>
          <p className="text-sm text-[var(--text-secondary)]">Letzter Run</p>
        </div>
        <button className="rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all">
          Volltext öffnen
        </button>
      </div>
      <div className="max-h-48 overflow-y-auto rounded-lg bg-[var(--bg-tertiary)] p-4 text-sm text-[var(--text-primary)] leading-relaxed">
        {report.slice(0, 1200) || "Noch kein Report generiert."}
      </div>
    </div>
  );
}

function scoreBadge(score?: number, variant: "opp" | "torp" = "opp") {
  if (score === undefined || score === null) return "bg-[var(--bg-tertiary)] text-[var(--text-muted)]";
  if (variant === "opp") {
    if (score >= 7) return "bg-[var(--accent-green)]/20 text-[var(--accent-green)]";
    if (score >= 5) return "bg-[var(--accent-amber)]/20 text-[var(--accent-amber)]";
    return "bg-[var(--accent-red)]/20 text-[var(--accent-red)]";
  }
  if (score >= 7) return "bg-[var(--accent-red)]/20 text-[var(--accent-red)]";
  if (score >= 5) return "bg-[var(--accent-amber)]/20 text-[var(--accent-amber)]";
  return "bg-[var(--accent-green)]/20 text-[var(--accent-green)]";
}

function heatmapCardBackground(item: WatchlistItem) {
  const opp = item.opportunity_score ?? 0;
  const torp = item.torpedo_score ?? 0;
  if (opp >= 6.5 && torp < 6) return "bg-emerald-500/5 border-emerald-500/30";
  if (torp >= 6.5 && opp < 6) return "bg-rose-500/5 border-rose-500/30";
  if (opp >= 6 && torp >= 6) return "bg-purple-500/5 border-purple-500/30";
  return "bg-[var(--bg-tertiary)] border-[var(--border)]";
}

function DeltaPill({ value }: { value?: number }) {
  if (value === undefined || value === null || value === 0) {
    return <span className="text-xs text-[var(--text-muted)]">0.0</span>;
  }
  const isPositive = value > 0;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold ${isPositive ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
      {isPositive ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {value.toFixed(1)}
    </span>
  );
}

function WatchlistHeatmap({ items, sparklines, concentrationWarning }: {
  items: WatchlistItem[];
  sparklines: Record<string, SparklinePoint[]>;
  concentrationWarning?: string | null;
}) {
  if (!items.length) {
    return (
      <div className="card p-6 text-center">
        <p className="text-sm text-[var(--text-muted)]">Watchlist leer – füge im Watchlist-Tab Ticker hinzu.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {concentrationWarning && (
        <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {concentrationWarning}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.slice(0, 9).map((item) => {
          const sparklineData = sparklines[item.ticker] || [];
          return (
            <div
              key={item.ticker}
              className={`rounded-2xl border p-4 transition-all hover:-translate-y-0.5 hover:shadow-lg ${heatmapCardBackground(item)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">{item.sector || "Unknown"}</p>
                  <Link href={`/watchlist/${item.ticker}`} className="text-2xl font-semibold text-[var(--text-primary)] hover:underline">
                    {item.ticker}
                  </Link>
                  <p className="text-sm text-[var(--text-secondary)]">{item.company_name || ""}</p>
                </div>
                {item.earnings_countdown !== undefined && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-secondary)]/60 px-3 py-1 text-xs text-[var(--text-secondary)]">
                    <CalendarIcon size={12} />
                    {item.earnings_countdown >= 0 ? `📅 ${item.earnings_countdown}T` : "📅 vorbei"}
                  </span>
                )}
              </div>

              <div className="mt-4 flex items-end justify-between gap-4">
                <div>
                  <p className="text-2xl font-bold text-[var(--text-primary)]">${item.price?.toFixed(2) ?? "--"}</p>
                  <p className={`text-sm font-semibold ${item.change_pct && item.change_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                    {item.change_pct ? `${item.change_pct.toFixed(2)}%` : "--"}
                  </p>
                </div>
                <div className="flex flex-col items-end text-xs text-[var(--text-muted)]">
                  <p>RSI {item.rsi?.toFixed(1) ?? "--"}</p>
                  <p className="capitalize">{item.trend || "-"}</p>
                </div>
              </div>

              <div className="mt-4 h-20 w-full">
                {sparklineData.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={sparklineData} margin={{ top: 8, bottom: 0, left: 0, right: 0 }}>
                      <Area
                        type="monotone"
                        dataKey="price"
                        stroke={(sparklineData.at(-1)?.price ?? 0) >= (sparklineData[0]?.price ?? 0) ? "#22c55e" : "#ef4444"}
                        fill={(sparklineData.at(-1)?.price ?? 0) >= (sparklineData[0]?.price ?? 0) ? "#22c55e33" : "#ef444433"}
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-[var(--text-muted)]">Keine Daten</div>
                )}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-black/20 p-3">
                  <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                    <span>Opportunity</span>
                    <DeltaPill value={item.opp_delta} />
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${scoreBadge(item.opportunity_score, "opp")}`}>
                      {item.opportunity_score?.toFixed(1) ?? "--"}
                    </span>
                    <div className="relative h-2 flex-1 rounded-full bg-black/20">
                      <div
                        className="absolute inset-y-0 rounded-full bg-[var(--accent-purple)]"
                        style={{ width: `${Math.min(100, Math.max(0, (item.opportunity_score ?? 0) * 10))}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="rounded-xl bg-black/10 p-3">
                  <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                    <span>Torpedo</span>
                    <DeltaPill value={item.torp_delta} />
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${scoreBadge(item.torpedo_score, "torp")}`}>
                      {item.torpedo_score?.toFixed(1) ?? "--"}
                    </span>
                    <div className="relative h-2 flex-1 rounded-full bg-black/20">
                      <div
                        className="absolute inset-y-0 rounded-full bg-[var(--accent-red)]"
                        style={{ width: `${Math.min(100, Math.max(0, (item.torpedo_score ?? 0) * 10))}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {item.notes && (
                <p className="mt-3 text-xs text-[var(--text-secondary)] line-clamp-2">{item.notes}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function OpportunitiesSection({ opportunities, onAdd }: { opportunities: OpportunityItem[]; onAdd: (item: OpportunityItem) => void }) {
  if (!opportunities.length) return null;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-[var(--text-primary)]">🔍 Opportunities — Earnings diese Woche</h3>
          <p className="text-sm text-[var(--text-secondary)]">Top-Kandidaten basierend auf Volatilität & RSI</p>
        </div>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {opportunities.slice(0, 5).map((item) => (
          <div key={item.ticker} className="rounded-2xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">{item.sector || "Unknown"}</p>
                <h4 className="text-xl font-semibold text-[var(--text-primary)]">{item.ticker}</h4>
                <p className="text-sm text-[var(--text-secondary)]">{item.name}</p>
              </div>
              <button
                onClick={() => onAdd(item)}
                className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
              >
                Zur Watchlist
              </button>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-3 text-sm text-[var(--text-secondary)]">
              <div>
                <p className="text-xs text-[var(--text-muted)]">RSI</p>
                <p className="text-[var(--text-primary)] font-semibold">{item.rsi?.toFixed(1) ?? "--"}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--text-muted)]">Vola%</p>
                <p className="text-[var(--text-primary)] font-semibold">{item.volatility?.toFixed(1) ?? "--"}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--text-muted)]">MCap</p>
                <p className="text-[var(--text-primary)] font-semibold">${item.market_cap_b?.toFixed(1) ?? "--"}B</p>
              </div>
            </div>
            <div className="mt-3 text-xs text-[var(--text-secondary)]">
              Earnings am {item.earnings_date || "?"}
            </div>
            {item.analysis && (
              <p className="mt-3 text-sm text-[var(--text-primary)]">{item.analysis}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<{
    macro: MacroSnapshot;
    overview: { indices: Record<string, IndexData>; sector_ranking_5d: SectorRank[]; macro: Record<string, IndexData> };
    report: string;
    watchlist: WatchlistItem[];
    concentrationWarning?: string | null;
    sectorDistribution?: Record<string, number>;
    opportunities: OpportunityItem[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [nextRefresh, setNextRefresh] = useState(60);
  const [sparklines, setSparklines] = useState<Record<string, SparklinePoint[]>>({});

  const loadData = useCallback(async () => {
    setRefreshing(true);
    const result = await getDashboardData();
    setData(result);
    setLoading(false);
    setRefreshing(false);
    setLastUpdate(new Date());
    setNextRefresh(60);
  }, []);

  const handleAddOpportunity = useCallback(
    async (item: OpportunityItem) => {
      try {
        await api.addTicker({
          ticker: item.ticker,
          company_name: item.name,
          sector: item.sector || "Unknown",
          notes: `Auto-import aus Opportunity-Scanner (${item.earnings_date || "?"})`,
        });
        await loadData();
      } catch (error) {
        console.error("Opportunity add error", item.ticker, error);
      }
    },
    [loadData]
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-Refresh Timer (alle 60 Sekunden)
  useEffect(() => {
    const interval = setInterval(() => {
      setNextRefresh((prev) => {
        if (prev <= 1) {
          loadData();
          return 60;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [loadData]);

  const watchlistKey = data?.watchlist?.map((item) => item.ticker).join("|") ?? "";

  useEffect(() => {
    if (!data?.watchlist?.length) return;
    const topTickers = data.watchlist.slice(0, 9).map((item) => item.ticker);
    const missing = topTickers.filter((ticker) => !sparklines[ticker]);
    if (!missing.length) return;

    let cancelled = false;
    (async () => {
      const results = await Promise.all(
        missing.map(async (ticker) => {
          try {
            const response = await api.getSparkline(ticker);
            return { ticker, data: response.data || [] };
          } catch (error) {
            console.error("Sparkline fetch error", ticker, error);
            return { ticker, data: [] };
          }
        })
      );
      if (cancelled) return;
      setSparklines((prev) => {
        const next = { ...prev };
        for (const entry of results) {
          next[entry.ticker] = entry.data;
        }
        return next;
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [watchlistKey, data?.watchlist, sparklines]);

  if (loading || !data) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <RefreshCw size={32} className="mx-auto mb-4 animate-spin text-[var(--accent-blue)]" />
          <p className="text-[var(--text-muted)]">Lade Dashboard-Daten...</p>
        </div>
      </div>
    );
  }

  const { macro, overview, report, watchlist, concentrationWarning, opportunities } = data;

  return (
    <div className="space-y-8 p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Dashboard</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2">Marktüberblick und Watchlist-Highlights</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end text-xs text-[var(--text-secondary)]">
            {lastUpdate && (
              <span>Zuletzt aktualisiert: {lastUpdate.toLocaleTimeString("de-DE")}</span>
            )}
            <span className="text-[var(--text-muted)]">Nächstes Update in {nextRefresh}s</span>
          </div>
          <button
            onClick={loadData}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "Lädt..." : "Aktualisieren"}
          </button>
        </div>
      </div>

      <MacroBanner macro={macro} />

      <section className="space-y-6">
        <h2 className="text-lg font-bold text-[var(--text-primary)]">Market Overview</h2>
        <IndexCards data={overview.indices} />
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <SectorTable sectors={overview.sector_ranking_5d || []} />
          <MacroProxies macro={overview.macro} />
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <BriefingPreview report={report} />
        <WatchlistHeatmap items={watchlist} sparklines={sparklines} concentrationWarning={concentrationWarning} />
      </section>

      <OpportunitiesSection opportunities={opportunities} onAdd={handleAddOpportunity} />
    </div>
  );
}
