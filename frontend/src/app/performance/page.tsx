"use client";

import { useState, useEffect } from "react";
import { TrendingUp, TrendingDown, Target, Award } from "lucide-react";
import { api } from "@/lib/api";

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

export default function PerformancePage() {
  const [performance, setPerformance] = useState<PerformanceData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPerformance();
  }, []);

  async function loadPerformance() {
    try {
      const data = await api.getPerformance();
      setPerformance(data.performance || []);
    } catch (error) {
      console.error("Performance fetch error", error);
    } finally {
      setLoading(false);
    }
  }

  const latest = performance[0] || {};
  const totalReviews = latest.total_reviews || 0;
  const accuracy = latest.accuracy_pct || 0;
  const bestCall = latest.best_call_ticker || "-";
  const bestReturn = latest.best_call_return || 0;
  const worstCall = latest.worst_call_ticker || "-";
  const worstReturn = latest.worst_call_return || 0;

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-[var(--text-muted)]">Lade Performance-Daten...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Performance</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Trefferquote & Reviews</h1>
        <p className="text-sm text-[var(--text-secondary)]">Wie gut sind unsere Earnings-Vorhersagen?</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-[var(--border)] bg-gradient-to-br from-[var(--bg-secondary)] to-[var(--bg-tertiary)] p-6">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Target size={16} />
            <p className="text-xs uppercase tracking-[0.3em]">Trefferquote</p>
          </div>
          <p
            className={`mt-4 text-4xl font-bold ${
              accuracy >= 70
                ? "text-[var(--accent-green)]"
                : accuracy >= 50
                ? "text-[var(--accent-amber)]"
                : "text-[var(--accent-red)]"
            }`}
          >
            {accuracy.toFixed(1)}%
          </p>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">
            {latest.correct_predictions || 0} / {totalReviews} korrekt
          </p>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Award size={16} />
            <p className="text-xs uppercase tracking-[0.3em]">Anzahl Reviews</p>
          </div>
          <p className="mt-4 text-4xl font-bold text-[var(--text-primary)]">{totalReviews}</p>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">Gesamt analysiert</p>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <TrendingUp size={16} />
            <p className="text-xs uppercase tracking-[0.3em]">Bester Call</p>
          </div>
          <p className="mt-4 text-2xl font-bold text-[var(--accent-green)]">{bestCall}</p>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">
            {bestReturn > 0 ? `+${bestReturn.toFixed(2)}%` : `${bestReturn.toFixed(2)}%`}
          </p>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <TrendingDown size={16} />
            <p className="text-xs uppercase tracking-[0.3em]">Schlechtester Call</p>
          </div>
          <p className="mt-4 text-2xl font-bold text-[var(--accent-red)]">{worstCall}</p>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">
            {worstReturn > 0 ? `+${worstReturn.toFixed(2)}%` : `${worstReturn.toFixed(2)}%`}
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
        <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-[var(--text-muted)]">
          Performance-Historie
        </h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Periode</th>
                <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Reviews</th>
                <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Korrekt</th>
                <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Trefferquote</th>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Bester Call</th>
                <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Schlechtester Call</th>
              </tr>
            </thead>
            <tbody>
              {performance.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-muted)]">
                    Noch keine Performance-Daten vorhanden.
                  </td>
                </tr>
              ) : (
                performance.map((item, idx) => (
                  <tr key={idx} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)]">
                    <td className="px-4 py-3 text-[var(--text-primary)]">{item.period || "-"}</td>
                    <td className="px-4 py-3 text-right text-[var(--text-primary)]">{item.total_reviews || 0}</td>
                    <td className="px-4 py-3 text-right text-[var(--text-primary)]">{item.correct_predictions || 0}</td>
                    <td
                      className={`px-4 py-3 text-right font-semibold ${
                        (item.accuracy_pct || 0) >= 70
                          ? "text-[var(--accent-green)]"
                          : (item.accuracy_pct || 0) >= 50
                          ? "text-[var(--accent-amber)]"
                          : "text-[var(--accent-red)]"
                      }`}
                    >
                      {item.accuracy_pct?.toFixed(1) || "0.0"}%
                    </td>
                    <td className="px-4 py-3 text-[var(--text-primary)]">
                      {item.best_call_ticker || "-"}{" "}
                      <span className="text-[var(--accent-green)]">
                        ({item.best_call_return ? `+${item.best_call_return.toFixed(2)}%` : "-"})
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-primary)]">
                      {item.worst_call_ticker || "-"}{" "}
                      <span className="text-[var(--accent-red)]">
                        ({item.worst_call_return ? `${item.worst_call_return.toFixed(2)}%` : "-"})
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
