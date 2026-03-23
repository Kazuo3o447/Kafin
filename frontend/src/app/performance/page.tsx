"use client";

import { useState, useEffect, useCallback } from "react";
import { TrendingUp, TrendingDown, Target, Award, Loader2, Plus, RefreshCw, Trash2, Info } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { cachedFetch, cacheAge } from "@/lib/clientCache";
import { CacheStatus } from "@/components/CacheStatus";

type PerformanceData = {
  period?: string;
  total_reviews?: number;
  correct_predictions?: number;
  accuracy_pct?: number;
  best_call_ticker?: string;
  best_call_return?: number;
  worst_call_ticker?: string;
  worst_call_return?: number;
};

type ShadowTrade = {
  id: string;
  ticker: string;
  quarter: string;
  signal_type: string;
  trade_direction: string;
  opportunity_score: number | null;
  torpedo_score: number | null;
  entry_price: number | null;
  entry_date: string | null;
  stop_loss_price: number | null;
  exit_price: number | null;
  exit_date: string | null;
  exit_reason: string | null;
  pnl_usd: number | null;
  pnl_percent: number | null;
  prediction_correct: boolean | null;
  status: string;
  current_price?: number | null;
  unrealized_pct?: number | null;
  trade_reason?: string | null;  // NEU
  manual_entry?: boolean | null; // NEU
};

type ShadowSummary = {
  open_count: number;
  closed_count: number;
  win_rate_pct: number;
  avg_pnl_pct: number;
  win_rate_by_signal: Record<string, { total: number; correct: number; win_rate_pct: number }>;
  best_trade: { ticker: string; pnl_pct: number } | null;
  worst_trade: { ticker: string; pnl_pct: number } | null;
  open_trades: ShadowTrade[];
  closed_trades: ShadowTrade[];
};

type RealTrade = {
  id: number;
  ticker: string;
  direction: "long" | "short";
  entry_date: string;
  entry_price: number;
  shares: number | null;
  stop_price: number | null;
  target_price: number | null;
  thesis: string | null;
  opportunity_score: number | null;
  torpedo_score: number | null;
  recommendation: string | null;
  snapshot_id: number | null;
  alpaca_order_id: string | null;
  exit_date: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  pnl: number | null;
  pnl_pct: number | null;
  active_signals: Array<{ signal_type: string; priority: number; headline: string }>;
};

type DecisionSnapshot = {
  id: number;
  ticker: string;
  created_at: string;
  opportunity_score: number | null;
  torpedo_score: number | null;
  recommendation: string | null;
  macro_regime: string | null;
  vix: number | null;
  credit_spread_bps: number | null;
  top_drivers: Array<{ factor: string; score: number; reasoning: string }> | null;
  top_risks: Array<{ factor: string; score: number; reasoning: string }> | null;
  price_at_decision: number | null;
  rsi_at_decision: number | null;
  iv_atm_at_decision: number | null;
  earnings_date: string | null;
  prompt_snapshot: string | null;
  model_used: string | null;
  price_t1: number | null;
  price_t5: number | null;
  price_t20: number | null;
  return_t1_pct: number | null;
  return_t5_pct: number | null;
  return_t20_pct: number | null;
  direction_correct_t1: boolean | null;
  direction_correct_t5: boolean | null;
  failure_hypothesis: string | null;
  data_quality_flag: string | null;
};

type AlpacaAccount = {
  configured: boolean;
  equity?: number;
  cash?: number;
  buying_power?: number;
  pnl_today?: number;
  status?: string;
  currency?: string;
};

type RealTradeFormState = {
  ticker: string;
  direction: "long" | "short";
  entry_date: string;
  entry_price: string;
  shares: string;
  stop_price: string;
  target_price: string;
  thesis: string;
  opportunity_score: string;
  torpedo_score: string;
  recommendation: string;
  exit_date: string;
  exit_price: string;
  exit_reason: string;
  notes: string;
  alpaca_order_id: string;
};

function buildEquityCurve(
  trades: ShadowTrade[]
): Array<{ date: string; cumulative: number; label: string }> {
  // Nur geschlossene Trades mit PnL
  const closed = trades
    .filter(t =>
      t.status === "closed"
      && t.pnl_percent != null
      && t.exit_date != null
    )
    .sort((a, b) =>
      new Date(a.exit_date!).getTime()
      - new Date(b.exit_date!).getTime()
    );

  if (closed.length === 0) return [];

  let cumulative = 0;
  return closed.map(t => {
    cumulative += t.pnl_percent ?? 0;
    return {
      date:       t.exit_date?.slice(0, 10) ?? "",
      cumulative: Math.round(cumulative * 10) / 10,
      label:      t.ticker,
    };
  });
}

function EquityCurveChart({
  trades,
}: {
  trades: ShadowTrade[];
}) {
  const data = buildEquityCurve(trades);
  if (data.length < 2) return (
    <div className="rounded-xl border border-dashed
                     border-[var(--border)] py-8
                     text-center">
      <p className="text-xs text-[var(--text-muted)]">
        Mindestens 2 abgeschlossene Trades nötig
      </p>
    </div>
  );

  const W = 560, H = 120, PAD = 12;
  const values = data.map(d => d.cumulative);
  const minV   = Math.min(0, ...values);
  const maxV   = Math.max(0, ...values);
  const range  = maxV - minV || 1;

  const toX = (i: number) =>
    PAD + (i / (data.length - 1)) * (W - PAD * 2);
  const toY = (v: number) =>
    H - PAD - ((v - minV) / range) * (H - PAD * 2);

  const zeroY  = toY(0);
  const isPos  = (data[data.length - 1].cumulative >= 0);
  const color  = isPos ? "var(--accent-green)"
                       : "var(--accent-red)";

  // Linien-Path
  const path = data
    .map((d, i) => `${i === 0 ? "M" : "L"}
      ${toX(i).toFixed(1)} ${toY(d.cumulative).toFixed(1)}`)
    .join(" ");

  // Fill-Path (zurück zur Zero-Linie)
  const fillPath = path
    + ` L ${toX(data.length - 1).toFixed(1)} ${zeroY.toFixed(1)}` 
    + ` L ${toX(0).toFixed(1)} ${zeroY.toFixed(1)} Z`;

  const lastVal = data[data.length - 1].cumulative;

  return (
    <div>
      <div className="flex items-baseline
                       justify-between mb-2">
        <p className="text-xs text-[var(--text-muted)]">
          Kumulierte PnL (Shadow Trades)
        </p>
        <span className={`text-sm font-bold font-mono ${
          lastVal >= 0
            ? "text-[var(--accent-green)]"
            : "text-[var(--accent-red)]"
        }`}>
          {lastVal >= 0 ? "+" : ""}{lastVal.toFixed(1)}%
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        className="overflow-visible"
      >
        {/* Zero-Linie */}
        <line
          x1={PAD} y1={zeroY}
          x2={W - PAD} y2={zeroY}
          stroke="var(--border)"
          strokeWidth="0.5"
          strokeDasharray="4 4"
        />
        {/* Fill */}
        <path
          d={fillPath}
          fill={color}
          opacity="0.08"
        />
        {/* Linie */}
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Letzter Punkt */}
        <circle
          cx={toX(data.length - 1)}
          cy={toY(lastVal)}
          r="3"
          fill={color}
        />
      </svg>
    </div>
  );
}

export default function PerformancePage() {
  const [performance, setPerformance] = useState<PerformanceData[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"track_record" | "shadow" | "my_trades" | "learning">("track_record");
  const [shadowData, setShadowData] = useState<ShadowSummary | null>(null);
  const [loadingShadow, setLoadingShadow] = useState(false);
  const [realTrades, setRealTrades] = useState<RealTrade[]>([]);
  const [loadingRealTrades, setLoadingRealTrades] = useState(false);
  const [snapshots, setSnapshots] = useState<DecisionSnapshot[]>([]);
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);
  const [alpacaAccount, setAlpacaAccount] = useState<AlpacaAccount | null>(null);
  const [alpacaPositions, setAlpacaPositions] = useState<Array<{
    ticker: string;
    qty: number;
    side: string;
    entry_price: number;
    current_price: number;
    market_value: number;
    unrealized_pnl: number;
    unrealized_pct: number;
  }>>([]);
  const [loadingAlpaca, setLoadingAlpaca] = useState(false);

  const [fromCache, setFromCache] = useState(false);
  const [dataAge, setDataAge] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [showRealTradeModal, setShowRealTradeModal] = useState(false);
  const [realTradeForm, setRealTradeForm] = useState<RealTradeFormState>({
    ticker: "",
    direction: "long",
    entry_date: "",
    entry_price: "",
    shares: "",
    stop_price: "",
    target_price: "",
    thesis: "",
    opportunity_score: "",
    torpedo_score: "",
    recommendation: "",
    exit_date: "",
    exit_price: "",
    exit_reason: "",
    notes: "",
    alpaca_order_id: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [tradeResult, setTradeResult] = useState<string | null>(null);

  useEffect(() => {
    loadPerformance();
  }, []);

  useEffect(() => {
    if (activeTab !== "shadow" || shadowData) return;
    setLoadingShadow(true);
    api
      .getShadowPortfolio()
      .then((data) => setShadowData(data))
      .catch((err) => console.error("Shadow portfolio fetch error", err))
      .finally(() => setLoadingShadow(false));
  }, [activeTab, shadowData]);

  useEffect(() => {
    if (activeTab !== "my_trades") return;
    if (realTrades.length === 0) {
      loadRealTrades();
    }
    if (!alpacaAccount) {
      loadAlpaca();
    }
  }, [activeTab, realTrades.length, alpacaAccount]);

  useEffect(() => {
    if (activeTab !== "learning" || snapshots.length > 0) return;
    loadSnapshots();
  }, [activeTab, snapshots.length]);

  const loadShadowPortfolio = useCallback(async () => {
    setLoadingShadow(true);
    try {
      const data = await api.getShadowPortfolio();
      setShadowData(data);
    } catch (err) {
      console.error("Shadow portfolio fetch error", err);
    } finally {
      setLoadingShadow(false);
    }
  }, []);

  const loadRealTrades = useCallback(async () => {
    setLoadingRealTrades(true);
    try {
      const data = await api.getRealTrades();
      setRealTrades(data.entries || []);
    } catch (err) {
      console.error("Real trades fetch error", err);
    } finally {
      setLoadingRealTrades(false);
    }
  }, []);

  const loadSnapshots = useCallback(async () => {
    setLoadingSnapshots(true);
    try {
      const data = await api.getDecisionSnapshots();
      setSnapshots(data.snapshots || []);
    } catch (err) {
      console.error("Decision snapshots fetch error", err);
    } finally {
      setLoadingSnapshots(false);
    }
  }, []);

  const loadAlpaca = useCallback(async () => {
    setLoadingAlpaca(true);
    try {
      const [account, positions] = await Promise.all([
        api.getAlpacaAccount(),
        api.getAlpacaPositions(),
      ]);
      setAlpacaAccount(account);
      setAlpacaPositions(positions.positions || []);
    } catch (err) {
      console.error("Alpaca fetch error", err);
    } finally {
      setLoadingAlpaca(false);
    }
  }, []);

  const loadPerformance = useCallback(async (invalidate = false) => {
    setLoading(!invalidate && performance.length === 0);
    if (invalidate) setRefreshing(true);
    try {
      const { data, fromCache: isCached } = await cachedFetch("performance:data", () => api.getPerformance(), 300);
      setPerformance(data?.performance || []);
      setFromCache(isCached);
      setDataAge(cacheAge("performance:data"));
    } catch (error) {
      console.error("Performance fetch error", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [performance.length]);

  const submitRealTrade = async () => {
    if (!realTradeForm.ticker || !realTradeForm.entry_price) {
      setTradeResult("Ticker und Entry-Preis sind Pflichtfelder.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        ticker: realTradeForm.ticker.trim().toUpperCase(),
        direction: realTradeForm.direction,
        entry_date: realTradeForm.entry_date || undefined,
        entry_price: Number(realTradeForm.entry_price),
        shares: realTradeForm.shares ? Number(realTradeForm.shares) : undefined,
        stop_price: realTradeForm.stop_price ? Number(realTradeForm.stop_price) : undefined,
        target_price: realTradeForm.target_price ? Number(realTradeForm.target_price) : undefined,
        thesis: realTradeForm.thesis || undefined,
        opportunity_score: realTradeForm.opportunity_score ? Number(realTradeForm.opportunity_score) : undefined,
        torpedo_score: realTradeForm.torpedo_score ? Number(realTradeForm.torpedo_score) : undefined,
        recommendation: realTradeForm.recommendation || undefined,
        exit_date: realTradeForm.exit_date || undefined,
        exit_price: realTradeForm.exit_price ? Number(realTradeForm.exit_price) : undefined,
        exit_reason: realTradeForm.exit_reason || undefined,
        notes: realTradeForm.notes || undefined,
        alpaca_order_id: realTradeForm.alpaca_order_id || undefined,
      };

      const resp = await api.createRealTrade(payload);
      if (resp?.success) {
        setTradeResult(`✓ Trade gespeichert: ${realTradeForm.ticker.toUpperCase()}`);
        setShowRealTradeModal(false);
        setRealTradeForm({
          ticker: "",
          direction: "long",
          entry_date: "",
          entry_price: "",
          shares: "",
          stop_price: "",
          target_price: "",
          thesis: "",
          opportunity_score: "",
          torpedo_score: "",
          recommendation: "",
          exit_date: "",
          exit_price: "",
          exit_reason: "",
          notes: "",
          alpaca_order_id: "",
        });
        await loadRealTrades();
      } else {
        setTradeResult(`Fehler: ${resp?.error || resp?.detail || "Unbekannt"}`);
      }
    } catch (err) {
      setTradeResult(`Fehler: ${err instanceof Error ? err.message : "Unbekannt"}`);
    } finally {
      setSubmitting(false);
    }
  };

  const latest = performance[0] || {};
  const totalReviews = latest.total_reviews || 0;
  const accuracy = latest.accuracy_pct || 0;
  const bestCall = latest.best_call_ticker || "-";
  const bestReturn = latest.best_call_return || 0;
  const worstCall = latest.worst_call_ticker || "-";
  const worstReturn = latest.worst_call_return || 0;

  const renderLoading = () => (
    <div className="flex h-96 items-center justify-center">
      <p className="text-[var(--text-muted)] flex items-center gap-2">
        <Loader2 className="h-5 w-5 animate-spin" /> Laden...
      </p>
    </div>
  );

  const renderTrackRecord = () => (
    <>
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${
              accuracy >= 70 ? "bg-[var(--accent-green)] bg-opacity-10" :
              accuracy >= 50 ? "bg-[var(--accent-amber)] bg-opacity-10" :
              "bg-[var(--accent-red)] bg-opacity-10"
            }`}>
              <Target size={24} className={
                accuracy >= 70 ? "text-[var(--accent-green)]" :
                accuracy >= 50 ? "text-[var(--accent-amber)]" :
                "text-[var(--accent-red)]"
              } />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Accuracy</p>
              <p
                className={`text-3xl font-bold ${
                  accuracy >= 70
                    ? "text-[var(--accent-green)]"
                    : accuracy >= 50
                    ? "text-[var(--accent-amber)]"
                    : "text-[var(--accent-red)]"
                }`}
              >
                {accuracy.toFixed(1)}%
              </p>
            </div>
          </div>
          <p className="text-sm text-[var(--text-secondary)]">
            {latest.correct_predictions || 0} / {totalReviews} korrekt
          </p>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-blue)] bg-opacity-10">
              <Award size={24} className="text-[var(--accent-blue)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Total Reviews</p>
              <p className="text-3xl font-bold text-[var(--text-primary)]">{totalReviews}</p>
            </div>
          </div>
          <p className="text-sm text-[var(--text-secondary)]">Gesamt analysiert</p>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-green)] bg-opacity-10">
              <TrendingUp size={24} className="text-[var(--accent-green)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Best Call</p>
              <p className="text-2xl font-bold text-[var(--text-primary)]">{bestCall}</p>
            </div>
          </div>
          <p className="text-sm font-semibold text-[var(--accent-green)]">
            {bestReturn > 0 ? `+${bestReturn.toFixed(2)}%` : `${bestReturn.toFixed(2)}%`}
          </p>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-red)] bg-opacity-10">
              <TrendingDown size={24} className="text-[var(--accent-red)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Worst Call</p>
              <p className="text-2xl font-bold text-[var(--text-primary)]">{worstCall}</p>
            </div>
          </div>
          <p className="text-sm font-semibold text-[var(--accent-red)]">
            {worstReturn > 0 ? `+${worstReturn.toFixed(2)}%` : `${worstReturn.toFixed(2)}%`}
          </p>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-bold text-[var(--text-primary)] mb-6">Performance History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Period</th>
                <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Reviews</th>
                <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Correct</th>
                <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Accuracy</th>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Best</th>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Worst</th>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Details</th>
              </tr>
            </thead>
            <tbody>
              {performance.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-[var(--text-muted)]">
                    Noch keine Performance-Daten vorhanden.
                  </td>
                </tr>
              ) : (
                performance.map((item, idx) => (
                  <tr key={idx} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors">
                    <td className="px-4 py-4 font-medium text-[var(--text-primary)]">{item.period || "-"}</td>
                    <td className="px-4 py-4 text-right text-[var(--text-primary)]">{item.total_reviews || 0}</td>
                    <td className="px-4 py-4 text-right text-[var(--text-primary)]">{item.correct_predictions || 0}</td>
                    <td className="px-4 py-4 text-right">
                      <span className={`inline-block px-3 py-1 rounded-lg text-sm font-bold ${
                        (item.accuracy_pct || 0) >= 70
                          ? "bg-[var(--accent-green)] bg-opacity-10 text-[var(--accent-green)]"
                          : (item.accuracy_pct || 0) >= 50
                          ? "bg-[var(--accent-amber)] bg-opacity-10 text-[var(--accent-amber)]"
                          : "bg-[var(--accent-red)] bg-opacity-10 text-[var(--accent-red)]"
                      }`}>
                        {item.accuracy_pct?.toFixed(1) || "0.0"}%
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span className="font-medium text-[var(--text-primary)]">{item.best_call_ticker || "-"}</span>
                      <span className="ml-2 text-sm font-semibold text-[var(--accent-green)]">
                        {item.best_call_return ? `+${item.best_call_return.toFixed(2)}%` : "-"}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span className="font-medium text-[var(--text-primary)]">{item.worst_call_ticker || "-"}</span>
                      <span className="ml-2 text-sm font-semibold text-[var(--accent-red)]">
                        {item.worst_call_return ? `${item.worst_call_return.toFixed(2)}%` : "-"}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      {item.best_call_ticker && (
                        <Link href={`/watchlist/${item.best_call_ticker}#track-record`} className="text-xs text-[var(--accent-blue)] hover:underline">
                          {item.best_call_ticker} ↗
                        </Link>
                      )}
                      {item.worst_call_ticker && (
                        <Link
                          href={`/watchlist/${item.worst_call_ticker}#track-record`}
                          className="ml-2 text-xs text-[var(--accent-red)] hover:underline"
                        >
                          {item.worst_call_ticker} ↗
                        </Link>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );

  const renderShadowKpiCard = (label: string, value: string | number, description: string, colorClass = "") => (
    <div className="card p-5">
      <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${colorClass}`}>{value}</p>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">{description}</p>
    </div>
  );

  const getWinRateColor = (value: number) => {
    if (value >= 60) return "text-emerald-400";
    if (value >= 40) return "text-amber-300";
    return "text-rose-400";
  };

  const renderShadowPortfolio = () => {
    if (loadingShadow || !shadowData) {
      return loadingShadow ? renderLoading() : (
        <div className="card p-8 text-center text-[var(--text-muted)]">Noch keine Daten geladen.</div>
      );
    }

    const bestTrade = shadowData.best_trade
      ? `${shadowData.best_trade.ticker} (${shadowData.best_trade.pnl_pct?.toFixed(1)}%)`
      : "Noch keine Daten";
    const worstTrade = shadowData.worst_trade
      ? `${shadowData.worst_trade.ticker} (${shadowData.worst_trade.pnl_pct?.toFixed(1)}%)`
      : "Noch keine Daten";

    const signalCards = Object.entries(shadowData.win_rate_by_signal || {}).filter(([, stats]) => stats.total > 0);

    return (
      <div className="space-y-8">
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {renderShadowKpiCard(
            "Win Rate",
            `${shadowData.win_rate_pct.toFixed(1)}%`,
            `${shadowData.closed_count} abgeschlossene Trades`,
            getWinRateColor(shadowData.win_rate_pct)
          )}
          {renderShadowKpiCard(
            "Ø PnL",
            `${shadowData.avg_pnl_pct >= 0 ? "+" : ""}${shadowData.avg_pnl_pct.toFixed(1)}%`,
            "Durchschnittlicher Trade",
            shadowData.avg_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"
          )}
          {renderShadowKpiCard("Bester Trade", bestTrade, "Top Performance", "text-emerald-300")}
          {renderShadowKpiCard("Schlechtester Trade", worstTrade, "Drawdown", "text-rose-300")}
        </div>

        {/* Equity Curve */}
        {shadowData && shadowData.closed_count > 0 && (
          <div className="card p-5">
            <EquityCurveChart trades={[...shadowData.open_trades, ...shadowData.closed_trades]} />
          </div>
        )}

        {signalCards.length > 0 && (
          <div>
            <h3 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">Win Rate nach Signal</h3>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {signalCards.map(([signal, stats]) => (
                <div key={signal} className="card p-4">
                  <p className="text-xs text-[var(--text-muted)]">{signal}</p>
                  <p className={`text-2xl font-bold ${getWinRateColor(stats.win_rate_pct)}`}>
                    {stats.win_rate_pct.toFixed(1)}%
                  </p>
                  <p className="text-sm text-[var(--text-secondary)]">{stats.correct}/{stats.total} korrekt</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">Offene Positionen ({shadowData.open_count})</h3>
          </div>
          {shadowData.open_count === 0 ? (
            <p className="text-[var(--text-muted)]">Keine offenen Positionen</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--border)]">
                  <tr>
                    <th className="px-3 py-3 text-left">Ticker</th>
                    <th className="px-3 py-3 text-left">Signal</th>
                    <th className="px-3 py-3 text-left">Richtung</th>
                    <th className="px-3 py-3 text-right">Entry</th>
                    <th className="px-3 py-3 text-right">Aktuell</th>
                    <th className="px-3 py-3 text-right">Unreal. PnL%</th>
                    <th className="px-3 py-3 text-right">Stop Loss</th>
                    <th className="px-3 py-3 text-left">Quarter</th>
                  </tr>
                </thead>
                <tbody>
                  {shadowData.open_trades.map((trade) => {
                    const unrealClass = trade.unrealized_pct == null
                      ? "text-[var(--text-muted)]"
                      : trade.unrealized_pct >= 0
                        ? "text-emerald-400"
                        : "text-rose-400";
                    const stopLossWarning =
                      trade.current_price != null &&
                      trade.stop_loss_price != null &&
                      trade.trade_direction === "long" &&
                      trade.current_price <= trade.stop_loss_price * 1.03;
                    return (
                      <tr key={trade.id} className="border-b border-[var(--border)]">
                        <td className="px-3 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="font-semibold text-[var(--text-primary)]">{trade.ticker}</span>
                            {trade.trade_reason && (
                              <span className="text-[10px] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)] text-[var(--text-muted)]">
                                {trade.trade_reason}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-[var(--text-primary)]">{trade.signal_type}</td>
                        <td className="px-3 py-3 capitalize text-[var(--text-secondary)]">{trade.trade_direction}</td>
                        <td className="px-3 py-3 text-right">${trade.entry_price?.toFixed(2) ?? "-"}</td>
                        <td className="px-3 py-3 text-right">${trade.current_price?.toFixed(2) ?? "-"}</td>
                        <td className={`px-3 py-3 text-right font-semibold ${unrealClass}`}>
                          {trade.unrealized_pct != null ? `${trade.unrealized_pct >= 0 ? "+" : ""}${trade.unrealized_pct.toFixed(1)}%` : "—"}
                        </td>
                        <td className={`px-3 py-3 text-right ${stopLossWarning ? "text-rose-400" : "text-[var(--text-secondary)]"}`}>
                          ${trade.stop_loss_price?.toFixed(2) ?? "-"}
                        </td>
                        <td className="px-3 py-3 text-[var(--text-secondary)]">{trade.quarter}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">Abgeschlossene Trades ({shadowData.closed_count})</h3>
          </div>
          {shadowData.closed_count === 0 ? (
            <p className="text-[var(--text-muted)]">Noch keine abgeschlossenen Trades</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--border)]">
                  <tr>
                    <th className="px-3 py-3 text-left">Ticker</th>
                    <th className="px-3 py-3 text-left">Signal</th>
                    <th className="px-3 py-3 text-right">Opp</th>
                    <th className="px-3 py-3 text-right">Torp</th>
                    <th className="px-3 py-3 text-right">Entry</th>
                    <th className="px-3 py-3 text-right">Exit</th>
                    <th className="px-3 py-3 text-right">PnL%</th>
                    <th className="px-3 py-3 text-center">Ergebnis</th>
                    <th className="px-3 py-3 text-left">Grund</th>
                  </tr>
                </thead>
                <tbody>
                  {shadowData.closed_trades.map((trade) => {
                    const pnlClass = trade.pnl_percent != null && trade.pnl_percent >= 0 ? "text-emerald-400" : "text-rose-400";
                    const resultIcon = trade.prediction_correct ? "✓" : "✗";
                    const resultClass = trade.prediction_correct ? "text-emerald-400" : "text-rose-400";
                    const reason = trade.exit_reason === "stop_loss" ? "Stop-Loss" : "Nach Earnings";
                    return (
                      <tr key={trade.id} className="border-b border-[var(--border)]">
                        <td className="px-3 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="font-semibold text-[var(--text-primary)]">{trade.ticker}</span>
                            {trade.trade_reason && (
                              <span className="text-[10px] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)] text-[var(--text-muted)]">
                                {trade.trade_reason}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-[var(--text-primary)]">{trade.signal_type}</td>
                        <td className="px-3 py-3 text-right">{trade.opportunity_score?.toFixed(1) ?? "-"}</td>
                        <td className="px-3 py-3 text-right">{trade.torpedo_score?.toFixed(1) ?? "-"}</td>
                        <td className="px-3 py-3 text-right">${trade.entry_price?.toFixed(2) ?? "-"}</td>
                        <td className="px-3 py-3 text-right">${trade.exit_price?.toFixed(2) ?? "-"}</td>
                        <td className={`px-3 py-3 text-right font-semibold ${pnlClass}`}>
                          {trade.pnl_percent != null ? `${trade.pnl_percent >= 0 ? "+" : ""}${trade.pnl_percent.toFixed(1)}%` : "-"}
                        </td>
                        <td className={`px-3 py-3 text-center text-lg ${resultClass}`}>{resultIcon}</td>
                        <td className="px-3 py-3 text-[var(--text-secondary)]">{reason}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-[var(--text-muted)]">
          ⚠ Shadow Portfolio — Simulierte Trades ohne echtes Kapital. Ausschließlich zur Kalibrierung der KI-Score-Qualität. Keine Handelsempfehlung.
        </p>
      </div>
    );
  };

  const refreshCurrentTab = () => {
    loadPerformance(true);
    if (activeTab === "shadow") {
      loadShadowPortfolio();
    } else if (activeTab === "my_trades") {
      loadRealTrades();
      loadAlpaca();
    } else if (activeTab === "learning") {
      loadSnapshots();
    }
  };

  const renderRealTrades = () => {
    const openCount = realTrades.filter((trade) => !trade.exit_date).length;
    const closedCount = realTrades.length - openCount;
    const totalPnl = realTrades.reduce((sum, trade) => sum + (trade.pnl || 0), 0);

    return (
      <div className="space-y-6">
        {tradeResult && (
          <div className={`rounded-xl border px-4 py-3 text-sm ${
            tradeResult.startsWith("✓")
              ? "border-[var(--accent-green)]/30 bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
              : "border-[var(--accent-red)]/30 bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
          }`}>
            {tradeResult}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">Meine Trades</p>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Echte Positionen & Trade-Ideen</h2>
            <p className="text-sm text-[var(--text-secondary)]">Verknüpft mit Alpaca Paper Trading, falls konfiguriert.</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => { setTradeResult(null); setShowRealTradeModal(true); }}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
            >
              <Plus size={14} />
              Trade erfassen
            </button>
            <button
              onClick={refreshCurrentTab}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
            >
              <RefreshCw size={14} />
              Aktualisieren
            </button>
          </div>
        </div>

        {loadingAlpaca ? (
          <div className="card p-6 text-sm text-[var(--text-muted)]">Alpaca-Daten werden geladen...</div>
        ) : alpacaAccount?.configured ? (
          <div className="card p-5 flex flex-wrap items-center gap-6">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Alpaca Paper Trading</p>
              <p className="mt-1 text-3xl font-bold font-mono text-[var(--text-primary)]">
                ${Number(alpacaAccount.equity || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Cash</p>
              <p className="font-mono text-sm text-[var(--text-primary)]">
                ${Number(alpacaAccount.cash || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">PnL heute</p>
              <p className={`font-mono text-sm ${(alpacaAccount.pnl_today || 0) >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                {(alpacaAccount.pnl_today || 0) >= 0 ? "+" : ""}${Number(alpacaAccount.pnl_today || 0).toFixed(0)}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Status</p>
              <p className="text-sm text-[var(--text-primary)]">{alpacaAccount.status || "—"}</p>
            </div>
          </div>
        ) : (
          <div className="card p-6 text-sm text-[var(--text-muted)]">Alpaca nicht konfiguriert. Paper Trading bleibt optional.</div>
        )}

        {alpacaPositions.length > 0 && (
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-[var(--text-primary)]">Offene Alpaca-Positionen</h3>
              <span className="text-xs text-[var(--text-muted)]">{alpacaPositions.length} Positionen</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {alpacaPositions.map((position) => (
                <div key={position.ticker} className="rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[var(--text-primary)]">{position.ticker}</span>
                    <span className="text-[10px] rounded px-2 py-0.5 bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">{position.side}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[var(--text-secondary)]">
                    <span>Qty</span><span className="text-right font-mono">{position.qty}</span>
                    <span>Entry</span><span className="text-right font-mono">${Number(position.entry_price || 0).toFixed(2)}</span>
                    <span>Current</span><span className="text-right font-mono">${Number(position.current_price || 0).toFixed(2)}</span>
                    <span>PnL%</span><span className={`text-right font-mono ${(position.unrealized_pct || 0) >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>{position.unrealized_pct >= 0 ? "+" : ""}{Number(position.unrealized_pct || 0).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          {[
            { label: "Echte Trades", value: realTrades.length },
            { label: "Offen", value: openCount },
            { label: "Geschlossen / PnL", value: `${closedCount} · ${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(0)}$` },
          ].map((item) => (
            <div key={item.label} className="card p-4">
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">{item.label}</p>
              <p className="mt-2 text-2xl font-bold text-[var(--text-primary)]">{item.value}</p>
            </div>
          ))}
        </div>

        {loadingRealTrades ? (
          <div className="card p-8 text-sm text-[var(--text-muted)]">Trades werden geladen...</div>
        ) : realTrades.length === 0 ? (
          <div className="card p-12 text-center text-sm text-[var(--text-muted)]">Noch keine Trades erfasst.</div>
        ) : (
          <div className="space-y-2">
            {realTrades.map((trade) => {
              const isOpen = !trade.exit_date;
              const pnlClass = trade.pnl == null ? "text-[var(--text-muted)]" : trade.pnl >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]";
              return (
                <div key={trade.id} className={`card p-4 border-l-4 ${isOpen ? "border-l-[var(--accent-blue)]" : trade.pnl && trade.pnl >= 0 ? "border-l-[var(--accent-green)]" : "border-l-[var(--accent-red)]"}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/research/${trade.ticker}`} className="font-mono font-bold text-[var(--accent-blue)]">{trade.ticker}</Link>
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${trade.direction === "long" ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]" : "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"}`}>{trade.direction.toUpperCase()}</span>
                      {isOpen && <span className="rounded px-2 py-0.5 text-[10px] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">OFFEN</span>}
                      {trade.active_signals?.map((sig, idx) => (
                        <span key={idx} title={sig.headline} className={`rounded px-2 py-0.5 text-[10px] ${sig.priority === 1 ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]" : "bg-amber-500/10 text-amber-400"}`}>
                          {sig.signal_type?.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                    <div className="flex items-center gap-3">
                      {trade.pnl != null && (
                        <span className={`font-mono text-sm font-bold ${pnlClass}`}>
                          {trade.pnl >= 0 ? "+" : ""}${Math.abs(trade.pnl).toFixed(0)}
                          {trade.pnl_pct != null && <span className="ml-1 text-xs">({trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(1)}%)</span>}
                        </span>
                      )}
                      <button
                        onClick={async () => {
                          await api.deleteRealTrade(trade.id);
                          await loadRealTrades();
                        }}
                        className="text-[var(--text-muted)] hover:text-[var(--accent-red)]"
                        title="Trade löschen"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
                    <span>Entry: ${Number(trade.entry_price || 0).toFixed(2)}</span>
                    {trade.exit_price != null && <span>Exit: ${Number(trade.exit_price || 0).toFixed(2)}</span>}
                    {trade.stop_price != null && <span>Stop: ${Number(trade.stop_price || 0).toFixed(2)}</span>}
                    {trade.target_price != null && <span>Target: ${Number(trade.target_price || 0).toFixed(2)}</span>}
                    <span>Entry-Datum: {trade.entry_date}</span>
                  </div>
                  {trade.thesis && <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{trade.thesis}</p>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const renderLearning = () => {
    const withT5 = snapshots.filter((snapshot) => snapshot.direction_correct_t5 !== null);
    const correct = withT5.filter((snapshot) => snapshot.direction_correct_t5).length;
    const t5Accuracy = withT5.length > 0 ? Math.round((correct / withT5.length) * 100) : null;
    const dataIssues = snapshots.filter((snapshot) => snapshot.data_quality_flag && snapshot.data_quality_flag !== "good").length;

    return (
      <div className="space-y-6">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">Lernkurve</p>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Decision Snapshots & Fehlermuster</h2>
          <p className="text-sm text-[var(--text-secondary)]">Snapshots werden später mit Outcomes aus Prompt 22 befüllt.</p>
        </div>

        {loadingSnapshots ? (
          <div className="card p-8 text-sm text-[var(--text-muted)]">Snapshots werden geladen...</div>
        ) : snapshots.length === 0 ? (
          <div className="card p-12 text-center text-sm text-[var(--text-muted)]">Noch keine Snapshots vorhanden.</div>
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-4">
              {[
                { label: "Snapshots gesamt", value: snapshots.length.toString() },
                { label: "T+5 Trefferquote", value: t5Accuracy !== null ? `${t5Accuracy}%` : "—" },
                { label: "Daten-Lücken", value: dataIssues.toString() },
                { label: "Ausgewertet", value: `${withT5.length}/${snapshots.length}` },
              ].map((item) => (
                <div key={item.label} className="card p-4">
                  <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">{item.label}</p>
                  <p className="mt-2 text-2xl font-bold text-[var(--text-primary)]">{item.value}</p>
                </div>
              ))}
            </div>

            <div className="space-y-2">
              {snapshots.slice(0, 20).map((snapshot) => (
                <div key={snapshot.id} className="card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-3">
                      <Link href={`/research/${snapshot.ticker}`} className="font-mono font-bold text-[var(--accent-blue)]">{snapshot.ticker}</Link>
                      <span className="text-xs text-[var(--text-muted)]">{new Date(snapshot.created_at).toLocaleDateString("de-DE")}</span>
                      <span className="rounded border border-[var(--border)] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">{snapshot.recommendation || "—"}</span>
                      {snapshot.data_quality_flag && snapshot.data_quality_flag !== "good" && (
                        <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-400">{snapshot.data_quality_flag.replace(/_/g, " ")}</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-3 font-mono text-xs">
                      {[
                        { label: "T+1", val: snapshot.return_t1_pct },
                        { label: "T+5", val: snapshot.return_t5_pct },
                        { label: "T+20", val: snapshot.return_t20_pct },
                      ].map((metric) => (
                        <span key={metric.label} className={metric.val == null ? "text-[var(--text-muted)]" : metric.val >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}>
                          {metric.label}: {metric.val == null ? "—" : `${metric.val >= 0 ? "+" : ""}${metric.val.toFixed(1)}%`}
                        </span>
                      ))}
                    </div>
                  </div>

                  {(snapshot.top_drivers?.length || snapshot.top_risks?.length) ? (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {snapshot.top_drivers?.slice(0, 3).map((driver, idx) => (
                        <span key={`d-${idx}`} title={driver.reasoning} className="rounded bg-[var(--accent-green)]/10 px-2 py-0.5 text-[10px] text-[var(--accent-green)]">↑ {driver.factor}</span>
                      ))}
                      {snapshot.top_risks?.slice(0, 2).map((risk, idx) => (
                        <span key={`r-${idx}`} title={risk.reasoning} className="rounded bg-[var(--accent-red)]/10 px-2 py-0.5 text-[10px] text-[var(--accent-red)]">↓ {risk.factor}</span>
                      ))}
                    </div>
                  ) : null}

                  {snapshot.failure_hypothesis && (
                    <p className="mt-2 text-xs italic text-amber-400">Hypothese: {snapshot.failure_hypothesis}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    );
  };

  const renderRealTradeModal = () => {
    if (!showRealTradeModal) return null;

    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
        onClick={() => setShowRealTradeModal(false)}
      >
        <div
          className="card mx-4 w-full max-w-3xl max-h-[90vh] overflow-y-auto p-6"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Neuen realen Trade erfassen</h2>
              <p className="text-xs text-[var(--text-secondary)]">Optionale Felder reichen, um Journal und Alpaca zu verbinden.</p>
            </div>
            <button onClick={() => setShowRealTradeModal(false)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">✕</button>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Ticker *</span>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm font-mono uppercase text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.ticker}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, ticker: e.target.value.toUpperCase() }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Direction</span>
              <select
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.direction}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, direction: e.target.value as "long" | "short" }))}
              >
                <option value="long">long</option>
                <option value="short">short</option>
              </select>
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Entry Date</span>
              <input
                type="date"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.entry_date}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, entry_date: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Entry Price *</span>
              <input
                type="number"
                step="0.0001"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.entry_price}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, entry_price: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Shares</span>
              <input
                type="number"
                step="0.0001"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.shares}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, shares: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Stop Price</span>
              <input
                type="number"
                step="0.0001"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.stop_price}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, stop_price: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Target Price</span>
              <input
                type="number"
                step="0.0001"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.target_price}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, target_price: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Opportunity Score</span>
              <input
                type="number"
                step="0.1"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.opportunity_score}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, opportunity_score: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Torpedo Score</span>
              <input
                type="number"
                step="0.1"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.torpedo_score}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, torpedo_score: e.target.value }))}
              />
            </label>

            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Recommendation</span>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.recommendation}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, recommendation: e.target.value }))}
              />
            </label>

            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Thesis</span>
              <textarea
                className="min-h-24 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.thesis}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, thesis: e.target.value }))}
              />
            </label>

            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Notes</span>
              <textarea
                className="min-h-20 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.notes}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, notes: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Exit Date</span>
              <input
                type="date"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.exit_date}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, exit_date: e.target.value }))}
              />
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Exit Price</span>
              <input
                type="number"
                step="0.0001"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.exit_price}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, exit_price: e.target.value }))}
              />
            </label>

            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Exit Reason</span>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.exit_reason}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, exit_reason: e.target.value }))}
              />
            </label>

            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Alpaca Order ID</span>
              <input
                type="text"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                value={realTradeForm.alpaca_order_id}
                onChange={(e) => setRealTradeForm((prev) => ({ ...prev, alpaca_order_id: e.target.value }))}
              />
            </label>
          </div>

          <div className="mt-5 flex gap-2">
            <button
              onClick={() => setShowRealTradeModal(false)}
              className="flex-1 rounded-lg border border-[var(--border)] py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]"
            >
              Abbrechen
            </button>
            <button
              onClick={submitRealTrade}
              disabled={submitting || !realTradeForm.ticker || !realTradeForm.entry_price}
              className="flex-1 rounded-lg bg-[var(--accent-blue)] py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? "Speichere…" : "Trade speichern"}
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-8 p-8">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-4xl font-bold text-[var(--text-primary)]">Performance</h1>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">KI-Trefferquote, Paper Trades, reale Trades und Lernkurve</p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/performance/lernpfade"
              className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]
                         hover:text-[var(--text-primary)] border border-[var(--border)]
                         rounded-lg px-3 py-1.5 transition-colors"
            >
              <TrendingUp size={13} />
              Lernpfade
            </Link>
            <button
              onClick={refreshCurrentTab}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
            >
              <RefreshCw size={14} />
              Aktualisieren
            </button>
          </div>
        </div>
        <div className="mt-2">
          <CacheStatus fromCache={fromCache} ageSeconds={dataAge} onRefresh={() => loadPerformance(true)} refreshing={refreshing || loading} />
        </div>
      </div>

      <div className="flex w-full items-center gap-2 rounded-xl bg-[var(--bg-tertiary)] p-1">
        {[
          { id: "track_record", label: "KI-Trefferquote" },
          { id: "shadow", label: "Paper Trades" },
          { id: "my_trades", label: "Meine Trades" },
          { id: "learning", label: "Lernkurve" },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-semibold transition ${
              activeTab === tab.id
                ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "track_record"
        ? (loading ? renderLoading() : renderTrackRecord())
        : activeTab === "shadow"
          ? renderShadowPortfolio()
          : activeTab === "my_trades"
            ? renderRealTrades()
            : renderLearning()}

      {renderRealTradeModal()}
    </div>
  );
}
