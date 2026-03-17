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
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-4xl font-bold text-[var(--text-primary)]">Performance</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">Track Record der Earnings-Predictions</p>
      </div>

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
              </tr>
            </thead>
            <tbody>
              {performance.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-[var(--text-muted)]">
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
