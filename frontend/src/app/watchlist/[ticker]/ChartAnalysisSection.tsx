"use client";

import { useState } from "react";
import { LineChart, Loader2, Target, Shield, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";

type ChartAnalysisResult = {
  ticker: string;
  price?: number;
  rsi?: number;
  trend?: string;
  support?: number;
  resistance?: number;
  sma_50?: number | null;
  sma_200?: number | null;
  volume_trend?: string;
  analysis?: string;
  error?: string;
};

export function ChartAnalysisSection({ ticker }: { ticker: string }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ChartAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getChartAnalysis(ticker);
      setResult(response);
    } catch (err) {
      console.error("Chart analysis error", err);
      setError("Analyse fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[var(--text-muted)]">
          <LineChart size={16} />
          <h2 className="text-sm font-semibold uppercase tracking-[0.3em]">Chartanalyse</h2>
        </div>
        <button
          onClick={runAnalysis}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <LineChart size={16} />}
          {loading ? "Analysiere..." : "Chartanalyse starten"}
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-[var(--accent-red)]">{error}</p>}

      {result && !loading && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-3 text-sm text-[var(--text-secondary)]">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3">
              <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Preis</p>
              <p className="text-xl font-semibold text-[var(--text-primary)]">${result.price?.toFixed(2) ?? "--"}</p>
              <p className="text-xs text-[var(--text-muted)]">Trend: {result.trend || "-"}</p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">
                <Target size={12} />
                RSI
              </div>
              <p className="text-xl font-semibold text-[var(--text-primary)]">{result.rsi?.toFixed(1) ?? "--"}</p>
              <p className="text-xs text-[var(--text-muted)]">Volume: {result.volume_trend || "-"}</p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">
                <Shield size={12} />
                Levels
              </div>
              <p className="text-xs text-[var(--text-muted)]">Support: <span className="text-[var(--text-primary)]">${result.support?.toFixed(2) ?? "--"}</span></p>
              <p className="text-xs text-[var(--text-muted)]">Resistance: <span className="text-[var(--text-primary)]">${result.resistance?.toFixed(2) ?? "--"}</span></p>
            </div>
          </div>

          {result.analysis ? (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4 text-sm leading-6 text-[var(--text-primary)] whitespace-pre-line">
              {result.analysis}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Noch keine Analyse vorhanden.</p>
          )}
        </div>
      )}
    </div>
  );
}
