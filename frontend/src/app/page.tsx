"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown, Activity, DollarSign, Percent, Circle, RefreshCw, ArrowDownRight, ArrowUpRight, Info, Calendar as CalendarIcon, Clock, AlertTriangle, Zap, Brain, ChevronRight, ChevronDown, ChevronUp, X } from "lucide-react";
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJSON<T>(endpoint: string, revalidate = 60): Promise<T> {
  const url = API_BASE ? `${API_BASE}${endpoint}` : endpoint;
  const res = await fetch(url, {
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function getLegacyFeedData(invalidate = false) {
  if (invalidate) cacheInvalidateAll();

  try {
    const [
      { data: macro, fromCache: macroFromCache },
      { data: overview },
      { data: report },
      { data: watchlistResp },
      { data: opportunitiesResp }
    ] = await Promise.all([
      cachedFetch("feed:macro", () => fetchJSON<MacroSnapshot>("/api/data/macro"), 120),
      cachedFetch("feed:overview", () => fetchJSON<{ indices: Record<string, IndexData>; sector_rankings: SectorRank[]; macro: Record<string, IndexData> }>("/api/data/market-overview"), 120),
      cachedFetch("feed:report", () => fetchJSON<{ report?: string }>("/api/reports/latest").catch(() => ({ report: "" })), 60),
      cachedFetch("feed:watchlist", () => fetchJSON<WatchlistResponse>("/api/watchlist/enriched").catch(() => ({ watchlist: [], concentration_warning: null, sector_distribution: {} })), 60),
      cachedFetch("feed:opportunities", () => fetchJSON<{ opportunities?: OpportunityItem[] }>("/api/opportunities").catch(() => ({ opportunities: [] })), 120),
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
    console.error("Feed fetch error", error);
    return {
      macro: {},
      overview: { indices: {}, sector_rankings: [], macro: {} },
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

function formatAge(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `vor ${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `vor ${minutes}m`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `vor ${hours}h`;

  return `vor ${Math.floor(hours / 24)}d`;
}

type SignalFeedItem = {
  ticker: string;
  signal_type: string;
  priority: number;
  headline: string;
  bullets?: string[];
  is_new?: boolean;
  is_resolved?: boolean;
  value?: number | null;
  threshold?: number | null;
  generated_at?: string;
  open_position?: {
    direction: "long" | "short";
    entry_price: number | null;
    shares: number | null;
    stop_price: number | null;
    target_price: number | null;
    entry_date: string;
  } | null;
  position_risk: "high" | "positive" | "neutral" | null;
};

type SignalPreparation = {
  ticker: string;
  name?: string;
  earnings_date?: string | null;
  analysis?: string;
  interest_score?: number | null;
};

type SignalFeedResponse = {
  signals: SignalFeedItem[];
  resolved_signals: SignalFeedItem[];
  preparation_setups: SignalPreparation[];
  today_synthesis: string;
  action_brief: string;
  is_market_hours: boolean;
  total_count: number;
  tickers_monitored: number;
  feed_generated_at: string;
  oldest_data_at?: string;
  config_snapshot?: Record<string, unknown>;
  macro_regime?: string;
};

type PaperTradeModalState = {
  signal: SignalFeedItem;
  qty: string;
  useStop: boolean;
  useTakeProfit: boolean;
};

function SignalFeedView() {
  const [feed, setFeed] = useState<SignalFeedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [briefRefreshing, setBriefRefreshing] = useState(false);
  const [briefExpanded, setBriefExpanded] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tradeModal, setTradeModal] = useState<PaperTradeModalState | null>(null);
  const [tradingInProgress, setTradingInProgress] = useState(false);
  const [tradeResult, setTradeResult] = useState<string | null>(null);

  const loadFeed = useCallback(async (forceRefresh = false) => {
    if (forceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError(null);
    try {
      const result = await api.getSignalsFeed(forceRefresh);
      setFeed(result);
    } catch (e: any) {
      setError(e?.message || "Signal Feed konnte nicht geladen werden.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  async function refreshActionBrief() {
    if (briefRefreshing) return;
    setBriefRefreshing(true);
    try {
      const result = await api.getSignalsFeed(true);
      setFeed(result);
    } catch (e: any) {
      setError(e?.message || "Handlungsempfehlung konnte nicht neu generiert werden.");
    } finally {
      setBriefRefreshing(false);
    }
  }

  async function executePaperTrade() {
    if (!tradeModal || tradingInProgress) return;
    const qty = parseFloat(tradeModal.qty);
    if (!qty || qty <= 0) return;

    setTradingInProgress(true);
    try {
      const sig = tradeModal.signal;
      const pos = sig.open_position;
      const direction = sig.signal_type === "setup_improving"
        ? "long"
        : sig.signal_type === "torpedo_rising"
          ? "short"
          : "long";

      let entryPrice = Number(pos?.entry_price ?? 0);
      if (!entryPrice || entryPrice <= 0) {
        try {
          const snapshot = await api.getQuickSnapshot(sig.ticker);
          entryPrice = Number(snapshot?.current_price ?? 1);
        } catch {
          entryPrice = 1;
        }
      }

      const alpacaResult = await api.openAlpacaPaperTrade({
        ticker: sig.ticker,
        direction,
        qty,
        stop_loss: tradeModal.useStop ? pos?.stop_price ?? undefined : undefined,
        take_profit: tradeModal.useTakeProfit ? pos?.target_price ?? undefined : undefined,
        signal_type: sig.signal_type,
        opportunity_score: Number(feed?.config_snapshot?.["torpedo_delta_min"] ?? 7),
        torpedo_score: 3,
      });

      if (alpacaResult.success) {
        await api.createRealTrade({
          ticker: sig.ticker,
          direction,
          entry_date: new Date().toISOString().slice(0, 10),
          entry_price: entryPrice,
          shares: qty,
          stop_price: tradeModal.useStop ? pos?.stop_price ?? undefined : undefined,
          target_price: tradeModal.useTakeProfit ? pos?.target_price ?? undefined : undefined,
          thesis: sig.headline,
          alpaca_order_id: alpacaResult.order_id || undefined,
        });
        setTradeResult(
          `✅ Paper Trade eröffnet: ${sig.ticker} ${direction.toUpperCase()} × ${qty} — Order ${alpacaResult.order_id?.slice(0, 8)}...`
        );
        setTradeModal(null);
      } else {
        setTradeResult(`❌ Fehler: ${alpacaResult.error || alpacaResult.detail || "Unbekannt"}`);
      }
    } catch (e: any) {
      setTradeResult(`❌ ${e?.message || "Unbekannter Fehler"}`);
    } finally {
      setTradingInProgress(false);
    }
  }

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const headlineSignals = feed?.signals ?? [];
  const prepSetups = feed?.preparation_setups ?? [];
  const resolvedSignals = feed?.resolved_signals ?? [];
  const loadedAt = feed?.feed_generated_at ? new Date(feed.feed_generated_at) : null;

  if (loading && !feed) {
    return (
      <div className="flex h-[70vh] items-center justify-center px-6">
        <div className="flex items-center gap-3 text-[var(--text-secondary)]">
          <RefreshCw size={18} className="animate-spin text-[var(--accent-blue)]" />
          <span>Signal Feed wird geladen…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">
              <Zap size={18} />
            </div>
            <div>
              <h1 className="text-4xl font-bold text-[var(--text-primary)]">Signal Feed</h1>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                Aktive Anomalien, Preparation Setups und Handlungsempfehlung
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-xs text-[var(--text-secondary)]">
            <div className="flex items-center gap-2">
              <Activity size={14} className={feed?.is_market_hours ? "text-[var(--accent-green)]" : "text-[var(--accent-amber)]"} />
              <span>{feed?.is_market_hours ? "Market Hours" : "Preparation Mode"}</span>
            </div>
          </div>
          <button
            onClick={() => loadFeed(true)}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-xl bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "Aktualisiere…" : "Refresh"}
          </button>
        </div>
      </div>

      {feed?.action_brief && (
        <div className="card border border-[var(--accent-blue)]/20">
          <div
            className="flex cursor-pointer items-center justify-between p-4"
            onClick={() => setBriefExpanded((e) => !e)}
          >
            <div className="flex items-center gap-2">
              <Brain size={14} className="text-[var(--accent-blue)]" />
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--accent-blue)]">
                Handlungsempfehlung
              </p>
              <span className="text-[10px] text-[var(--text-muted)]">{formatAge(feed.feed_generated_at)}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  refreshActionBrief();
                }}
                disabled={briefRefreshing}
                title="Neu generieren (Reasoner)"
                className="flex items-center gap-1 rounded border border-[var(--accent-blue)]/30 px-2 py-0.5 text-[10px] text-[var(--accent-blue)] hover:opacity-80 disabled:opacity-40"
              >
                <RefreshCw size={10} className={briefRefreshing ? "animate-spin" : ""} />
                Aktualisieren
              </button>
              {briefExpanded ? (
                <ChevronUp size={14} className="text-[var(--text-muted)]" />
              ) : (
                <ChevronDown size={14} className="text-[var(--text-muted)]" />
              )}
            </div>
          </div>

          {briefExpanded && (
            <div className="border-t border-[var(--border)] px-4 pb-4 pt-3">
              <p className="text-sm leading-relaxed text-[var(--text-primary)]">{feed.action_brief}</p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-200">
          <div className="flex items-center gap-2 font-semibold text-red-300">
            <AlertTriangle size={16} />
            Feed-Ladefehler
          </div>
          <p className="mt-1 text-red-200/80">{error}</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        {[
          { label: "Aktive Signale", value: feed?.total_count ?? headlineSignals.length, icon: Zap },
          { label: "Ticker überwacht", value: feed?.tickers_monitored ?? 0, icon: Activity },
          { label: "Regime", value: feed?.macro_regime || "UNKNOWN", icon: Brain },
          { label: "Letztes Update", value: loadedAt ? loadedAt.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "—", icon: Clock },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="card p-5">
              <div className="mb-3 flex items-center gap-2 text-[var(--text-muted)]">
                <Icon size={14} />
                <span className="text-xs uppercase tracking-[0.24em]">{item.label}</span>
              </div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">{item.value}</div>
            </div>
          );
        })}
      </div>

      <section className="card p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">Today Synthesis</p>
            <h2 className="mt-1 text-lg font-bold text-[var(--text-primary)]">Handlung in einem Satz</h2>
          </div>
          <Link href="/settings" className="text-xs text-[var(--accent-blue)] hover:opacity-80">
            Feed Config →
          </Link>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">{feed?.today_synthesis || "Keine aktiven Signale."}</p>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">Active Signals</p>
            <h2 className="text-lg font-bold text-[var(--text-primary)]">Was gerade zählt</h2>
          </div>
          <span className="text-xs text-[var(--text-muted)]">
            {headlineSignals.length} Ergebnisse
          </span>
        </div>

        {headlineSignals.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {headlineSignals.map((signal) => (
              <div key={`${signal.ticker}-${signal.signal_type}`} className="card p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Link href={`/research/${signal.ticker}`} className="text-lg font-bold text-[var(--accent-blue)] hover:opacity-80">
                      {signal.ticker}
                    </Link>
                    <p className="mt-1 text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">
                      {signal.signal_type.replaceAll("_", " ")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {signal.is_new && <span className="rounded-full bg-[var(--accent-green)]/10 px-2 py-1 text-[10px] font-semibold text-[var(--accent-green)]">NEW</span>}
                    {signal.is_resolved && <span className="rounded-full bg-[var(--accent-amber)]/10 px-2 py-1 text-[10px] font-semibold text-[var(--accent-amber)]">RESOLVED</span>}
                    {/* Position-Badge wenn offene Position vorhanden */}
                    {signal.open_position && (
                      <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                        signal.position_risk === "high"
                          ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
                          : signal.position_risk === "positive"
                            ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                            : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                      }`}>
                        {signal.open_position.direction === "long" ? "▲ Long" : "▼ Short"}
                        {" "}${signal.open_position.entry_price?.toFixed(0)}
                      </span>
                    )}
                    <span className="rounded-full border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--text-muted)]">
                      P{signal.priority}
                    </span>
                    {signal.priority === 1 && !signal.is_resolved && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setTradeModal({
                            signal,
                            qty: "1",
                            useStop: Boolean(signal.open_position?.stop_price),
                            useTakeProfit: Boolean(signal.open_position?.target_price),
                          });
                        }}
                        title="Alpaca Paper Trade eröffnen"
                        className="whitespace-nowrap rounded border border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 px-2 py-1 text-[10px] font-medium text-[var(--accent-blue)] hover:bg-[var(--accent-blue)]/20"
                      >
                        Paper Trade
                      </button>
                    )}
                  </div>
                </div>

                <p className="mt-4 text-sm font-medium text-[var(--text-primary)]">{signal.headline}</p>

                {signal.bullets?.length ? (
                  <ul className="mt-4 space-y-2 text-sm text-[var(--text-secondary)]">
                    {signal.bullets.map((bullet) => (
                      <li key={bullet} className="flex gap-2">
                        <ChevronRight size={14} className="mt-0.5 shrink-0 text-[var(--accent-blue)]" />
                        <span>{bullet.replace(/^•\s*/, "")}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="card p-8 text-sm text-[var(--text-muted)]">
            Keine aktiven Signale im Feed.
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">Preparation Setups</p>
            <h2 className="text-lg font-bold text-[var(--text-primary)]">Vorbereitung für die nächste Session</h2>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {prepSetups.length ? prepSetups.map((setup) => (
            <Link
              key={setup.ticker}
              href={`/research/${setup.ticker}`}
              className="card p-5 transition-transform hover:-translate-y-0.5 hover:border-[var(--accent-blue)]/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-bold text-[var(--text-primary)]">{setup.ticker}</p>
                  <p className="text-xs text-[var(--text-muted)]">{setup.name || setup.ticker}</p>
                </div>
                <ChevronRight size={16} className="text-[var(--text-muted)]" />
              </div>
              <p className="mt-4 text-sm text-[var(--text-secondary)]">{setup.analysis || "Setup in Vorbereitung."}</p>
              <div className="mt-4 flex items-center justify-between text-xs text-[var(--text-muted)]">
                <span>{setup.earnings_date ? new Date(setup.earnings_date).toLocaleDateString("de-DE") : "—"}</span>
                <span>{setup.interest_score != null ? `Score ${setup.interest_score.toFixed(1)}` : "Score —"}</span>
              </div>
            </Link>
          )) : (
            <div className="card p-6 text-sm text-[var(--text-muted)]">Keine Prep-Setups verfügbar.</div>
          )}
        </div>
      </section>

      <section className="card p-6">
        <div className="mb-3 flex items-center gap-2 text-[var(--text-muted)]">
          <AlertTriangle size={15} className="text-[var(--accent-amber)]" />
          <p className="text-xs font-semibold uppercase tracking-[0.24em]">Resolved Signals</p>
        </div>
        {resolvedSignals.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {resolvedSignals.map((signal) => (
              <div key={`${signal.ticker}-${signal.signal_type}`} className="rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
                <div className="flex items-center justify-between gap-2">
                  <Link href={`/research/${signal.ticker}`} className="font-semibold text-[var(--accent-blue)] hover:opacity-80">
                    {signal.ticker}
                  </Link>
                  <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">resolved</span>
                </div>
                <p className="mt-2 text-sm text-[var(--text-primary)]">{signal.headline}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">Noch keine gelösten Signale im 24h-Fenster.</p>
        )}
      </section>

      {tradeModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setTradeModal(null)}
        >
          <div
            className="card mx-4 w-full max-w-sm space-y-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold text-[var(--text-primary)]">
                Paper Trade: {tradeModal.signal.ticker}
              </p>
              <button onClick={() => setTradeModal(null)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <X size={16} />
              </button>
            </div>

            <div className="rounded-lg bg-[var(--bg-tertiary)] p-3 text-xs text-[var(--text-secondary)]">
              {tradeModal.signal.headline}
            </div>

            <div className="space-y-2">
              <label className="text-xs text-[var(--text-muted)]">Anzahl Shares / Kontrakte</label>
              <input
                type="number"
                min="1"
                step="1"
                value={tradeModal.qty}
                onChange={(e) => setTradeModal((prev) => prev ? { ...prev, qty: e.target.value } : null)}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                autoFocus
              />
            </div>

            {tradeModal.signal.open_position && (
              <div className="space-y-2 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3 text-xs text-[var(--text-secondary)]">
                <p className="font-semibold text-[var(--text-primary)]">Risikoeinstellungen</p>
                <label className="flex items-center justify-between gap-3">
                  <span>Stop-Loss übernehmen</span>
                  <input
                    type="checkbox"
                    checked={tradeModal.useStop}
                    onChange={(e) => setTradeModal((prev) => prev ? { ...prev, useStop: e.target.checked } : null)}
                  />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span>Take-Profit übernehmen</span>
                  <input
                    type="checkbox"
                    checked={tradeModal.useTakeProfit}
                    onChange={(e) => setTradeModal((prev) => prev ? { ...prev, useTakeProfit: e.target.checked } : null)}
                  />
                </label>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={executePaperTrade}
                disabled={tradingInProgress || !tradeModal.qty}
                className="flex-1 rounded-lg bg-[var(--accent-blue)] py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-40"
              >
                {tradingInProgress ? <RefreshCw size={14} className="mx-auto animate-spin" /> : "Paper Trade eröffnen"}
              </button>
              <button
                onClick={() => setTradeModal(null)}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
              >
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}

      {tradeResult && (
        <div
          className={`fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border px-4 py-3 text-sm font-medium shadow-lg ${
            tradeResult.startsWith("✅")
              ? "border-[var(--accent-green)]/30 bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
              : "border-[var(--accent-red)]/30 bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
          }`}
          onClick={() => setTradeResult(null)}
        >
          {tradeResult}
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return <SignalFeedView />;
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

function LegacyIndexGrid({ data }: { data: Record<string, IndexData> }) {
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

function LegacySectorGrid({ sectors }: { sectors: SectorRank[] }) {
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
          <h3 className="text-lg font-bold text-[var(--text-primary)]">Legacy Briefing</h3>
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
        {items.slice(0, 9).map((item, idx) => {
          const sparklineData = sparklines[item.ticker] || [];
          return (
            <div
              key={`${item.ticker}-${idx}`}
              className={`min-h-0 overflow-hidden rounded-2xl border p-4 transition-all hover:-translate-y-0.5 hover:shadow-lg ${heatmapCardBackground(item)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">{item.sector || "Unknown"}</p>
                  <Link href={`/research/${item.ticker}`} className="text-2xl font-semibold text-[var(--text-primary)] hover:underline">
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

              <div className="mt-3 flex items-end justify-between gap-4">
                <div>
                  <p className="text-xl font-bold text-[var(--text-primary)] truncate">${item.price?.toFixed(2) ?? "--"}</p>
                  <p className={`text-sm font-semibold ${item.change_pct && item.change_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                    {item.change_pct ? `${item.change_pct.toFixed(2)}%` : "--"}
                  </p>
                </div>
                <div className="flex flex-col items-end text-xs text-[var(--text-muted)]">
                  <p>RSI {item.rsi?.toFixed(1) ?? "--"}</p>
                  <p className="capitalize">{item.trend || "-"}</p>
                </div>
              </div>

              <div className="mt-3 h-16 w-full">
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

              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
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
        {opportunities.slice(0, 5).map((item, idx) => (
          <div key={`${item.ticker}-${idx}`} className="rounded-2xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4">
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

function RegimePulse({ macro }: { macro: MacroSnapshot }) {
  const vix = macro.vix ?? 0;
  const cs = macro.credit_spread_bps ?? 0;
  const regime = macro.regime ?? "Neutral";
  const isRiskOn = regime.toLowerCase().includes("risk") && regime.toLowerCase().includes("on");
  const isRiskOff = regime.toLowerCase().includes("risk") && regime.toLowerCase().includes("off");

  return (
    <div className={`flex items-center gap-3 rounded-xl px-4 py-3
                     border ${
      isRiskOn  ? "border-[var(--accent-green)]/30 bg-[var(--accent-green)]/5"
    : isRiskOff ? "border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5"
    : "border-[var(--border)] bg-[var(--bg-secondary)]"
    }`}>
      <div className={`h-3 w-3 rounded-full ${
        isRiskOn  ? "bg-[var(--accent-green)] shadow-[0_0_8px_var(--accent-green)]"
      : isRiskOff ? "bg-[var(--accent-red)] shadow-[0_0_8px_var(--accent-red)]"
      : "bg-amber-400"
      }`} />
      <span className={`text-sm font-semibold ${
        isRiskOn  ? "text-[var(--accent-green)]"
      : isRiskOff ? "text-[var(--accent-red)]"
      : "text-amber-400"
      }`}>
        {regime.toUpperCase()}
      </span>
      <span className="text-xs text-[var(--text-muted)]">
        VIX {vix.toFixed(1)} · Credit {cs.toFixed(0)}bp
      </span>
    </div>
  );
}

function AlertStrip({ alerts }: {
  alerts: { ticker: string; message: string; color: string }[]
}) {
  if (!alerts.length) return null;
  const colorMap: Record<string, string> = {
    red:   "bg-[var(--accent-red)]/8 border-l-[var(--accent-red)] text-[var(--accent-red)]",
    amber: "bg-amber-500/8 border-l-amber-500 text-amber-400",
    green: "bg-[var(--accent-green)]/8 border-l-[var(--accent-green)] text-[var(--accent-green)]",
  };
  return (
    <div className="card p-4 space-y-1.5">
      <p className="text-[10px] font-semibold uppercase
                    tracking-widest text-[var(--text-muted)] mb-2">
        Heute aufpassen
      </p>
      {alerts.map((a, i) => (
        <div key={i}
             className={`flex items-center gap-3 rounded-lg
                          px-3 py-2 border-l-2 text-xs
                          ${colorMap[a.color] || colorMap.amber}`}>
          <Link href={`/research/${a.ticker}`}
                className="font-semibold hover:underline">
            {a.ticker}
          </Link>
          <span className="text-[var(--text-secondary)]">
            {a.message}
          </span>
        </div>
      ))}
    </div>
  );
}

function TopSetups({ watchlist }: { watchlist: WatchlistItem[] }) {
  const sorted = [...watchlist]
    .filter(w => w.opportunity_score != null)
    .sort((a, b) =>
      (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0)
    );
  const best = sorted[0];
  const worst = [...watchlist]
    .filter(w => w.torpedo_score != null)
    .sort((a, b) =>
      (b.torpedo_score ?? 0) - (a.torpedo_score ?? 0)
    )[0];
  if (!best && !worst) return null;
  return (
    <div className="grid grid-cols-2 gap-3">
      {best && (
        <Link href={`/research/${best.ticker}`}
              className="card p-4 hover:border-[var(--accent-green)]/50
                         transition-colors">
          <p className="text-[10px] text-[var(--text-muted)]
                         uppercase tracking-wider mb-1">
            Bestes Setup
          </p>
          <p className="text-lg font-bold font-mono
                         text-[var(--accent-green)]">
            {best.ticker}
          </p>
          <p className="text-xs text-[var(--text-secondary)]">
            Opp {best.opportunity_score?.toFixed(1)} ·{" "}
            {best.company_name || ""}
          </p>
        </Link>
      )}
      {worst && (
        <Link href={`/research/${worst.ticker}`}
              className="card p-4 hover:border-[var(--accent-red)]/50
                         transition-colors">
          <p className="text-[10px] text-[var(--text-muted)]
                         uppercase tracking-wider mb-1">
            Höchstes Risiko
          </p>
          <p className="text-lg font-bold font-mono
                         text-[var(--accent-red)]">
            {worst.ticker}
          </p>
          <p className="text-xs text-[var(--text-secondary)]">
            Torp {worst.torpedo_score?.toFixed(1)} ·{" "}
            {worst.company_name || ""}
          </p>
        </Link>
      )}
    </div>
  );
}

function buildLegacyAlerts(
  watchlist: WatchlistItem[]
): { ticker: string; message: string;
    color: "red"|"amber"|"green" }[] {
  const alerts: ReturnType<typeof buildLegacyAlerts> = [];
  for (const w of watchlist) {
    // Earnings ≤5T
    if (w.earnings_countdown != null
        && w.earnings_countdown >= 0
        && w.earnings_countdown <= 5) {
      alerts.push({
        ticker: w.ticker,
        message: `Earnings in ${
          w.earnings_countdown === 0
            ? "HEUTE" : w.earnings_countdown + " Tagen"
        }`,
        color: "red",
      });
    }
    // Torpedo stark gestiegen
    if ((w.torp_delta ?? 0) >= 1.5) {
      alerts.push({
        ticker: w.ticker,
        message: `Torpedo +${w.torp_delta?.toFixed(1)} — Risiko steigt`,
        color: "red",
      });
    }
    // Earnings ≤14T
    if (w.earnings_countdown != null
        && w.earnings_countdown > 5
        && w.earnings_countdown <= 14) {
      alerts.push({
        ticker: w.ticker,
        message: `Earnings in ${w.earnings_countdown} Tagen`,
        color: "amber",
      });
    }
  }
  return alerts.sort((a, b) =>
    (a.color === "red" ? 0 : 1) - (b.color === "red" ? 0 : 1)
  ).slice(0, 5);
}

function LegacyFeedPage() {
  const [data, setData] = useState<{
    macro: MacroSnapshot;
    overview: { indices: Record<string, IndexData>; sector_rankings: SectorRank[]; macro: Record<string, IndexData> };
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
    const result = await getLegacyFeedData();
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
          <p className="text-[var(--text-muted)]">Lade Daten...</p>
        </div>
      </div>
    );
  }

  const { macro, overview, report, watchlist, concentrationWarning, opportunities } = data;

  return (
    <div className="space-y-4 p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Legacy View</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2">Signal-Setup für heute</p>
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

      <div className="space-y-4">

        {/* 1. Regime-Pulse — 1 Zeile */}
        <RegimePulse macro={macro} />

        {/* 2. Alert-Streifen */}
        <AlertStrip alerts={buildLegacyAlerts(watchlist)} />

        {/* 3. Beste Setups + Höchstes Risiko */}
        <TopSetups watchlist={watchlist} />

        {/* 4. Earnings diese Woche (kompakt) */}
        {watchlist.filter(w =>
          w.earnings_countdown != null
          && w.earnings_countdown >= 0
          && w.earnings_countdown <= 7
        ).length > 0 && (
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10px] font-semibold uppercase
                         tracking-widest text-[var(--text-muted)]">
                Earnings diese Woche
              </p>
              <Link href="/earnings"
                    className="text-xs text-[var(--accent-blue)]
                               hover:underline">
                Alle →
              </Link>
            </div>
            <div className="flex flex-wrap gap-2">
              {watchlist
                .filter(w =>
                  w.earnings_countdown != null
                  && w.earnings_countdown >= 0
                  && w.earnings_countdown <= 7
                )
                .sort((a, b) =>
                  (a.earnings_countdown ?? 99)
                  - (b.earnings_countdown ?? 99)
                )
                .map(w => (
                  <Link key={w.ticker}
                        href={`/research/${w.ticker}`}
                        className="flex items-center gap-2
                                   rounded-lg bg-[var(--bg-tertiary)]
                                   px-3 py-2 hover:bg-[var(--bg-elevated)]">
                    <span className="text-sm font-mono font-semibold
                                      text-[var(--accent-blue)]">
                      {w.ticker}
                    </span>
                    <span className="text-xs text-amber-400">
                      {w.earnings_countdown === 0
                        ? "HEUTE"
                        : `in ${w.earnings_countdown}T`}
                    </span>
                  </Link>
                ))}
            </div>
          </div>
        )}

        {/* 5. SPY + VIX + Credit (3 Zahlen) */}
        <div className="grid grid-cols-3 gap-3">
          {["SPY", "^VIX"].map(sym => {
            const d = overview.indices?.[sym]
                    || overview.macro?.[sym];
            if (!d) return null;
            return (
              <div key={sym} className="card p-3 text-center">
                <p className="text-[10px] text-[var(--text-muted)]">
                  {sym}
                </p>
                <p className="text-lg font-bold font-mono
                               text-[var(--text-primary)]">
                  {d.price?.toFixed(2) ?? "—"}
                </p>
                <p className={`text-xs font-mono ${
                  (d.change_1d_pct ?? 0) >= 0
                    ? "text-[var(--accent-green)]"
                  : "text-[var(--accent-red)]"
                }`}>
                  {d.change_1d_pct != null
                    ? `${d.change_1d_pct >= 0 ? "+" : ""}${d.change_1d_pct.toFixed(2)}%` 
                    : "—"}
                </p>
              </div>
            );
          })}
          <div className="card p-3 text-center">
            <p className="text-[10px] text-[var(--text-muted)]">
              Credit Spread
            </p>
            <p className="text-lg font-bold font-mono
                           text-[var(--text-primary)]">
              {macro.credit_spread_bps?.toFixed(0) ?? "—"}bp
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              HY-Spread
            </p>
          </div>
        </div>

        {/* 6. Briefing (kompakt, aufklappbar) */}
        {report && report !== "Noch kein Briefing." && (
          <details className="card p-4">
            <summary className="cursor-pointer text-xs
                                 text-[var(--text-muted)]
                                 select-none hover:text-[var(--text-primary)]">
              Legacy Briefing ▸
            </summary>
            <p className="mt-3 text-xs text-[var(--text-secondary)]
                           leading-relaxed whitespace-pre-wrap
                           max-h-40 overflow-y-auto">
              {report.slice(0, 600)}
              {report.length > 600 ? "…" : ""}
            </p>
          </details>
        )}

      </div>
    </div>
  );
}
