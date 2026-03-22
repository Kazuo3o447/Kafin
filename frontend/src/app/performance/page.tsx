"use client";

import { useState, useEffect, useCallback } from "react";
import { TrendingUp, TrendingDown, Target, Award, Loader2 } from "lucide-react";
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
  const [activeTab, setActiveTab] = useState<"track_record" | "shadow">("track_record");
  const [shadowData, setShadowData] = useState<ShadowSummary | null>(null);
  const [loadingShadow, setLoadingShadow] = useState(false);

  const [fromCache, setFromCache] = useState(false);
  const [dataAge, setDataAge] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Trade Modal State
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [tradeForm, setTradeForm] = useState({
    ticker: "",
    direction: "long" as "long" | "short",
    trade_reason: "",
    notes: "",
  });
  const [tradeReasons, setTradeReasons] = useState<string[]>([]);
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

  // Load trade reasons
  useEffect(() => {
    fetch("/api/shadow/trade-reasons")
      .then(r => r.json())
      .then(d => setTradeReasons(d.reasons || []))
      .catch(() => {});
  }, []);

  // Submit handler
  const submitTrade = async () => {
    if (!tradeForm.ticker || !tradeForm.trade_reason) {
      return;
    }
    setSubmitting(true);
    try {
      const resp = await fetch(
        "/api/shadow/manual-trade",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticker:         tradeForm.ticker.toUpperCase(),
            direction:      tradeForm.direction,
            trade_reason:   tradeForm.trade_reason,
          }),
        }
      );
      const data = await resp.json();
      if (data.success) {
        setTradeResult(
          `✓ Trade eröffnet: ${tradeForm.ticker} ` 
          + `${tradeForm.direction.toUpperCase()}` 
        );
        setShowTradeModal(false);
        // Reload
        loadPerformance(true);
      } else {
        setTradeResult(
          `Fehler: ${data.reason || data.error || "?"}` 
        );
      }
    } catch {
      setTradeResult("Verbindungsfehler");
    } finally {
      setSubmitting(false);
    }
  };

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

  // Trade Modal Component
  if (showTradeModal) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
        onClick={() => setShowTradeModal(false)}
      >
        <div
          className="card p-6 w-full max-w-md mx-4"
          onClick={e => e.stopPropagation()}
        >
          <h2 className="text-base font-bold text-[var(--text-primary)] mb-4">
            Shadow-Trade eröffnen
          </h2>

          {/* Ticker */}
          <div className="mb-3">
            <label className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block mb-1">
              Ticker
            </label>
            <input
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm font-mono text-[var(--text-primary)] uppercase placeholder:normal-case placeholder:text-[var(--text-muted)] outline-none focus:border-[var(--accent-blue)]"
              placeholder="z.B. NVDA"
              value={tradeForm.ticker}
              onChange={e => setTradeForm(f => ({
                ...f, ticker: e.target.value
              }))}
            />
          </div>

          {/* Richtung */}
          <div className="mb-3">
            <label className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block mb-1">
              Richtung
            </label>
            <div className="flex gap-2">
              {(["long", "short"] as const).map(d => (
                <button
                  key={d}
                  onClick={() => setTradeForm(f =>
                    ({ ...f, direction: d })
                  )}
                  className={`flex-1 rounded-lg py-2 text-sm font-semibold border transition-colors ${
                    tradeForm.direction === d
                      ? d === "long"
                        ? "border-[var(--accent-green)] bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                        : "border-[var(--accent-red)] bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
                      : "border-[var(--border)] text-[var(--text-muted)]"
                  }`}
                >
                  {d === "long" ? "Long ▲" : "Short ▼"}
                </button>
              ))}
            </div>
          </div>

          {/* Trade-Grund */}
          <div className="mb-4">
            <label className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block mb-1">
              Hauptgrund *
            </label>
            <select
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
              value={tradeForm.trade_reason}
              onChange={e => setTradeForm(f => ({
                ...f, trade_reason: e.target.value
              }))}
            >
              <option value="">— Grund wählen —</option>
              {tradeReasons.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>

          {/* Buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowTradeModal(false)}
              className="flex-1 rounded-lg border border-[var(--border)] py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]"
            >
              Abbrechen
            </button>
            <button
              onClick={submitTrade}
              disabled={
                submitting
                || !tradeForm.ticker
                || !tradeForm.trade_reason
              }
              className="flex-1 rounded-lg bg-[var(--accent-blue)] py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? "Öffne…" : "Trade eröffnen"}
            </button>
          </div>

          {tradeResult && (
            <p className={`text-xs mt-3 text-center ${
              tradeResult.startsWith("✓")
                ? "text-[var(--accent-green)]"
                : "text-[var(--accent-red)]"
            }`}>
              {tradeResult}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-8">
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-[var(--text-primary)]">Performance</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-2">Track Record & Shadow Portfolio</p>
          </div>
          <button
            onClick={() => {
              setTradeResult(null);
              setShowTradeModal(true);
            }}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
          >
            + Trade eröffnen
          </button>
        </div>
        <div className="mt-2"><CacheStatus fromCache={fromCache} ageSeconds={dataAge} onRefresh={() => loadPerformance(true)} refreshing={refreshing || loading} /></div>
      </div>

      <div className="flex w-full items-center gap-2 rounded-xl bg-[var(--bg-tertiary)] p-1">
        <button
          className={`flex-1 rounded-lg px-4 py-2 text-sm font-semibold transition ${
            activeTab === "track_record"
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow"
              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          }`}
          onClick={() => setActiveTab("track_record")}
        >
          Track Record
        </button>
        <button
          className={`flex-1 rounded-lg px-4 py-2 text-sm font-semibold transition ${
            activeTab === "shadow"
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow"
              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          }`}
          onClick={() => setActiveTab("shadow")}
        >
          Shadow Portfolio
        </button>
      </div>

      {activeTab === "track_record" ? (loading ? renderLoading() : renderTrackRecord()) : renderShadowPortfolio()}
    </div>
  );
}
