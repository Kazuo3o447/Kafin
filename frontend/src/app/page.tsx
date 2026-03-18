"use client";

import { useState, useEffect, useCallback } from "react";
import { TrendingUp, TrendingDown, Activity, DollarSign, Percent, Circle, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

import { ArrowDownRight, ArrowUpRight, Info, Circle as CircleIcon } from "lucide-react";

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
  notes?: string;
  opportunity_score?: number;
  torpedo_score?: number;
  price?: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(endpoint: string, revalidate = 60): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function getDashboardData() {
  try {
    const [macro, overview, report, watchlist] = await Promise.all([
      fetchJSON<MacroSnapshot>("/api/data/macro", 120),
      fetchJSON<{ indices: Record<string, IndexData>; sector_ranking_5d: SectorRank[]; macro: Record<string, IndexData> }>(
        "/api/data/market-overview",
        120
      ),
      fetchJSON<{ report?: string }>("/api/reports/latest", 30).catch(() => ({ report: "" })),
      fetchJSON<WatchlistItem[]>("/api/watchlist", 30).catch(() => []),
    ]);

    return { macro, overview, report: report.report || "Noch kein Briefing.", watchlist };
  } catch (error) {
    console.error("Dashboard fetch error", error);
    return {
      macro: {},
      overview: { indices: {}, sector_ranking_5d: [], macro: {} },
      report: "API nicht erreichbar.",
      watchlist: [] as WatchlistItem[],
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

function WatchlistGrid({ items }: { items: WatchlistItem[] }) {
  if (!items.length) return (
    <div className="card p-6 text-center">
      <p className="text-sm text-[var(--text-muted)]">Watchlist leer – füge im Watchlist-Tab Ticker hinzu.</p>
    </div>
  );

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-[var(--text-primary)]">Watchlist Highlights</h3>
          <p className="text-sm text-[var(--text-secondary)]">{items.length} aktive Ticker</p>
        </div>
      </div>
      <div className="space-y-3">
        {items.slice(0, 6).map((item) => (
          <div key={item.ticker} className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-4 transition-all hover:shadow-sm">
            <div className="flex items-center gap-4">
              <div>
                <h4 className="text-lg font-bold text-[var(--text-primary)]">{item.ticker}</h4>
                <p className="text-xs text-[var(--text-muted)]">{item.company_name || ""}</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-sm font-bold text-[var(--text-primary)]">${item.price?.toFixed(2) || "--"}</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <p className="text-xs text-[var(--text-muted)] mb-1">OPP</p>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-bold ${
                    (item.opportunity_score ?? 0) >= 7 ? "bg-[var(--accent-green)] bg-opacity-10 text-[var(--accent-green)]" :
                    (item.opportunity_score ?? 0) >= 5 ? "bg-[var(--accent-amber)] bg-opacity-10 text-[var(--accent-amber)]" :
                    "bg-[var(--accent-red)] bg-opacity-10 text-[var(--accent-red)]"
                  }`}>
                    {item.opportunity_score?.toFixed(1) ?? "--"}
                  </span>
                </div>
                <div className="text-center">
                  <p className="text-xs text-[var(--text-muted)] mb-1">TORP</p>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-bold ${
                    (item.torpedo_score ?? 0) >= 7 ? "bg-[var(--accent-red)] bg-opacity-10 text-[var(--accent-red)]" :
                    (item.torpedo_score ?? 0) >= 5 ? "bg-[var(--accent-amber)] bg-opacity-10 text-[var(--accent-amber)]" :
                    "bg-[var(--accent-green)] bg-opacity-10 text-[var(--accent-green)]"
                  }`}>
                    {item.torpedo_score?.toFixed(1) ?? "--"}
                  </span>
                </div>
              </div>
            </div>
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
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [nextRefresh, setNextRefresh] = useState(60);

  const loadData = useCallback(async () => {
    setRefreshing(true);
    const result = await getDashboardData();
    setData(result);
    setLoading(false);
    setRefreshing(false);
    setLastUpdate(new Date());
    setNextRefresh(60);
  }, []);

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

  const { macro, overview, report, watchlist } = data;

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
        <WatchlistGrid items={watchlist} />
      </section>
    </div>
  );
}
