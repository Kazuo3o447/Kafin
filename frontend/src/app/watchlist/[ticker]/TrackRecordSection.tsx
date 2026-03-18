"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { Trophy, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

export type TrackRecordEntry = {
  quarter: string;
  status: "reviewed" | "pending";
  report_date: string | null;
  earnings_date: string | null;
  opportunity_score: number | null;
  torpedo_score: number | null;
  recommendation: string | null;
  actual_eps: number | null;
  actual_eps_consensus: number | null;
  actual_surprise_percent: number | null;
  actual_revenue: number | null;
  actual_revenue_consensus: number | null;
  stock_price_pre: number | null;
  stock_reaction_1d_percent: number | null;
  stock_reaction_5d_percent: number | null;
  prediction_correct: boolean | null;
  score_accuracy: string | null;
  review_text: string | null;
  lessons_learned: string | null;
};

export type TrackRecordSummary = {
  total_predictions: number;
  correct: number;
  wrong: number;
  win_rate_pct: number;
  current_streak: number;
  torpedo_warnings_total: number;
  torpedo_warnings_correct: number;
  torpedo_calibration_msg: string;
};

export type TrackRecordData = {
  ticker: string;
  summary: TrackRecordSummary | null;
  history: TrackRecordEntry[];
};

const recommendationMap: Record<string, { label: string; short: string; className: string }> = {
  "STRONG BUY": { label: "STRONG BUY", short: "STR. BUY", className: "bg-emerald-500/20 text-emerald-300" },
  "BUY MIT ABSICHERUNG": { label: "BUY MIT ABSICHERUNG", short: "BUY/ABS.", className: "bg-green-500/20 text-green-300" },
  WATCH: { label: "WATCH", short: "WATCH", className: "bg-yellow-500/20 text-yellow-300" },
  "KEIN TRADE": { label: "KEIN TRADE", short: "KEIN TRADE", className: "bg-gray-500/20 text-gray-300" },
  "POTENTIELLER SHORT": { label: "POTENTIELLER SHORT", short: "POT. SHORT", className: "bg-orange-500/20 text-orange-300" },
  "STRONG SHORT": { label: "STRONG SHORT", short: "STR. SHORT", className: "bg-rose-500/20 text-rose-300" },
};

function formatPercentage(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

function formatRevenue(value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (value >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(1)}B`;
  }
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(0)}M`;
  }
  return `$${value.toFixed(0)}`;
}

function formatEPS(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(2)}`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    const date = new Date(value);
    return date.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "short",
      year: "2-digit",
    });
  } catch {
    return value;
  }
}

function recommendationBadge(rec: string | null) {
  if (!rec) {
    return <span className="rounded-full px-3 py-1 text-xs bg-gray-500/20 text-gray-300">—</span>;
  }
  const key = rec.toUpperCase();
  const config = recommendationMap[key];
  if (!config) {
    return <span className="rounded-full px-3 py-1 text-xs bg-gray-500/20 text-gray-300">{rec}</span>;
  }
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${config.className}`}>
      {config.short}
    </span>
  );
}

function streakBadge(streak: number) {
  if (streak >= 2) {
    return <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs text-emerald-300">🔥 {streak} in Folge richtig</span>;
  }
  if (streak <= -2) {
    return <span className="rounded-full bg-rose-500/15 px-3 py-1 text-xs text-rose-300">⚠ {Math.abs(streak)} in Folge falsch</span>;
  }
  return null;
}

const CustomScatterPoint = ({ cx, cy, payload }: any) => {
  const color = payload.reaction > 0 ? "#22c55e" : payload.reaction < 0 ? "#ef4444" : "#a3a3a3";
  return <circle cx={cx} cy={cy} r={5} fill={color} stroke="none" />;
};

export function TrackRecordSection({ ticker }: { ticker: string }) {
  const [data, setData] = useState<TrackRecordData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  useEffect(() => {
    async function loadTrackRecord() {
      try {
        const response = await api.getTickerTrackRecord(ticker);
        setData(response);
      } catch (error) {
        console.error("Track record fetch error", error);
        setData({ ticker, summary: null, history: [] });
      } finally {
        setLoading(false);
      }
    }
    loadTrackRecord();
  }, [ticker]);

  const reviewedCount = data?.history.filter((entry) => entry.status === "reviewed").length || 0;
  const scatterData = useMemo(() => {
    return (
      data?.history
        .filter((entry) => entry.status === "reviewed" && entry.torpedo_score !== null && entry.stock_reaction_1d_percent !== null)
        .map((entry) => ({
          torpedo: entry.torpedo_score as number,
          reaction: entry.stock_reaction_1d_percent as number,
          quarter: entry.quarter,
        })) || []
    );
  }, [data]);

  if (loading) {
    return (
      <section id="track-record" className="card p-6">
        <p className="text-sm text-[var(--text-muted)]">Track Record wird geladen...</p>
      </section>
    );
  }

  if (!data || data.history.length === 0) {
    return (
      <section id="track-record" className="card p-6">
        <p className="text-sm text-[var(--text-muted)]">Keine Track-Record-Daten verfügbar.</p>
      </section>
    );
  }

  const summary = data.summary;

  return (
    <section id="track-record" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">📊 Track Record</p>
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Letzte {data.history.length} Earnings-Zyklen</h2>
        </div>
      </div>

      {(!summary || reviewedCount < 2) ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6 text-sm text-[var(--text-secondary)]">
          Noch zu wenig Daten für einen Track Record. Nach dem nächsten Post-Earnings-Review erscheint hier die Trefferquote.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
            <div className="flex items-center gap-3 text-[var(--text-muted)]">
              <Trophy size={18} />
              <span className="text-sm font-semibold uppercase tracking-[0.3em]">Win Rate</span>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <div>
                <p className={`text-4xl font-bold ${
                  summary.win_rate_pct >= 60
                    ? "text-emerald-400"
                    : summary.win_rate_pct >= 40
                    ? "text-yellow-400"
                    : "text-rose-400"
                }`}>
                  {summary.win_rate_pct.toFixed(1)}%
                </p>
                <p className="text-sm text-[var(--text-secondary)]">
                  {summary.correct} von {summary.total_predictions} korrekt
                </p>
              </div>
              {streakBadge(summary.current_streak)}
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
            <div className="flex items-center gap-3 text-[var(--text-muted)]">
              <AlertTriangle size={18} />
              <span className="text-sm font-semibold uppercase tracking-[0.3em]">Torpedo-Kalibrierung</span>
            </div>
            <p className="mt-4 text-lg font-semibold text-[var(--text-primary)]">
              {summary.torpedo_calibration_msg}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-2">Torpedo ≥ 6 → tatsächlich negativ?</p>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-[var(--border)] text-[var(--text-secondary)]">
              <tr>
                <th className="px-4 py-3 text-left">Quartal</th>
                <th className="px-4 py-3 text-left">Datum</th>
                <th className="px-4 py-3 text-right">Opp</th>
                <th className="px-4 py-3 text-right">Torp</th>
                <th className="px-4 py-3 text-left">Empfehlung</th>
                <th className="px-4 py-3 text-right">1T-Reaktion</th>
                <th className="px-4 py-3 text-right">5T-Reaktion</th>
                <th className="px-4 py-3 text-center">✓/✗</th>
              </tr>
            </thead>
            <tbody>
              {(data?.history || []).map((entry) => {
                const isReviewed = entry.status === "reviewed";
                const isExpanded = expandedRow === entry.quarter;
                const borderClass = !isReviewed
                  ? "opacity-60 italic"
                  : entry.prediction_correct === true
                  ? "border-l-2 border-emerald-500"
                  : entry.prediction_correct === false
                  ? "border-l-2 border-rose-500"
                  : "";

                return (
                  <Fragment key={entry.quarter}>
                    <tr
                      className={`transition-colors ${borderClass} ${isReviewed ? "cursor-pointer hover:bg-[var(--bg-tertiary)]" : ""}`}
                      onClick={() => {
                        if (!isReviewed) return;
                        setExpandedRow(isExpanded ? null : entry.quarter);
                      }}
                    >
                      <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{entry.quarter}</td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">{formatDate(entry.report_date)}</td>
                      <td className="px-4 py-3 text-right text-[var(--text-primary)]">{formatNumber(entry.opportunity_score)}</td>
                      <td className="px-4 py-3 text-right text-[var(--text-primary)]">{formatNumber(entry.torpedo_score)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">{recommendationBadge(entry.recommendation)}</div>
                      </td>
                      <td className={`px-4 py-3 text-right ${
                        (entry.stock_reaction_1d_percent ?? 0) > 0
                          ? "text-emerald-400"
                          : (entry.stock_reaction_1d_percent ?? 0) < 0
                          ? "text-rose-400"
                          : "text-[var(--text-secondary)]"
                      }`}>
                        {formatPercentage(entry.stock_reaction_1d_percent)}
                      </td>
                      <td className={`px-4 py-3 text-right ${
                        (entry.stock_reaction_5d_percent ?? 0) > 0
                          ? "text-emerald-400"
                          : (entry.stock_reaction_5d_percent ?? 0) < 0
                          ? "text-rose-400"
                          : "text-[var(--text-secondary)]"
                      }`}>
                        {formatPercentage(entry.stock_reaction_5d_percent)}
                      </td>
                      <td className="px-4 py-3 text-center text-lg">
                        {entry.prediction_correct === true && <span className="text-emerald-400">✓</span>}
                        {entry.prediction_correct === false && <span className="text-rose-400">✗</span>}
                        {entry.prediction_correct === null && <span className="text-[var(--text-muted)]">—</span>}
                      </td>
                    </tr>
                    {isReviewed && isExpanded && (
                      <tr className="bg-[var(--bg-tertiary)]">
                        <td colSpan={8} className="px-6 pb-6">
                          <div className={`rounded-xl border ${
                            entry.prediction_correct === false ? "border-rose-500/40" : "border-[var(--border)]"
                          } bg-[var(--bg-secondary)] p-4 mt-2`}>
                            <div className="grid gap-4 md:grid-cols-2">
                              <div>
                                <h4 className="text-sm font-semibold text-[var(--text-primary)]">KI-PROGNOSE</h4>
                                <div className="mt-2 space-y-1 text-sm text-[var(--text-secondary)]">
                                  <p>Opp-Score: {formatNumber(entry.opportunity_score)}</p>
                                  <p>Torpedo-Score: {formatNumber(entry.torpedo_score)}</p>
                                  <p>Empfehlung: {entry.recommendation || "—"}</p>
                                  <p>Report vom: {formatDate(entry.report_date)}</p>
                                </div>
                              </div>
                              <div>
                                <h4 className="text-sm font-semibold text-[var(--text-primary)]">TATSÄCHLICHES ERGEBNIS</h4>
                                <div className="mt-2 space-y-1 text-sm text-[var(--text-secondary)]">
                                  <p>
                                    EPS: {formatEPS(entry.actual_eps)} (Konsens: {formatEPS(entry.actual_eps_consensus)})
                                  </p>
                                  <p>EPS-Surprise: {formatPercentage(entry.actual_surprise_percent)}</p>
                                  <p>Revenue: {formatRevenue(entry.actual_revenue)} ({formatRevenue(entry.actual_revenue_consensus)})</p>
                                  <p>1T-Reaktion: {formatPercentage(entry.stock_reaction_1d_percent)}</p>
                                  <p>5T-Reaktion: {formatPercentage(entry.stock_reaction_5d_percent)}</p>
                                </div>
                              </div>
                            </div>
                            {entry.lessons_learned && (
                              <div className="mt-4">
                                <p className={`text-sm font-semibold ${
                                  entry.prediction_correct === false ? "text-rose-300" : "text-[var(--text-secondary)]"
                                }`}>
                                  {entry.prediction_correct === false
                                    ? "Was hätte man beachten müssen?"
                                    : "Lessons Learned"}
                                </p>
                                <p className="mt-1 text-sm text-[var(--text-primary)]">{entry.lessons_learned}</p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {scatterData.length >= 3 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-[var(--text-primary)]">Torpedo-Score vs. Kursreaktion</p>
              <p className="text-xs text-[var(--text-muted)]">Ideale Kalibrierung: hoher Torpedo-Score → negative Reaktion</p>
            </div>
          </div>
          <div className="mt-4 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis type="number" dataKey="torpedo" domain={[0, 10]} name="Torpedo" tick={{ fill: "var(--text-secondary)" }} label={{ value: "Torpedo-Score", position: "insideBottom", offset: -5, fill: "var(--text-secondary)" }} />
                <YAxis type="number" dataKey="reaction" name="Reaktion" tick={{ fill: "var(--text-secondary)" }} label={{ value: "1T-Reaktion (%)", angle: -90, position: "insideLeft", fill: "var(--text-secondary)" }} />
                <ReferenceLine y={0} stroke="#a3a3a3" strokeDasharray="4 4" />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ payload }) => {
                  if (!payload || payload.length === 0) return null;
                  const point = payload[0].payload;
                  return (
                    <div className="rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 text-xs text-[var(--text-primary)]">
                      {point.quarter}: Torp {point.torpedo.toFixed(1)} → {formatPercentage(point.reaction)}
                    </div>
                  );
                }} />
                <Scatter data={scatterData} shape={<CustomScatterPoint />} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}
