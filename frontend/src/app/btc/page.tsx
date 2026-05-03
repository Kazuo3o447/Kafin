"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { RefreshCw, TrendingUp, TrendingDown, Minus,
         ArrowLeft, Brain, Activity, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { TickerChatBlock } from "@/app/research/[ticker]/page";

type BtcSnapshot = {
  price: {
    price: number | null;
    change_7d_pct: number | null;
    high_14d: number | null;
    low_14d: number | null;
    trend: string | null;
  };
  open_interest: { total_oi_usd: number | null; change_24h_pct: number | null } | null;
  funding_rate:  { avg_funding_rate_pct: number | null; interpretation: string | null } | null;
  long_short:    { long_pct: number | null; short_pct: number | null } | null;
  dxy: number | null;
  fetched_at: string;
};

type BtcReport = { date: string | null; report: string | null; generated_at: string };

function fmt(n: number | null, digits = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("de-DE", { maximumFractionDigits: digits });
}

export default function BtcPage() {
  const [snapshot, setSnapshot] = useState<BtcSnapshot | null>(null);
  const [report, setReport]     = useState<BtcReport | null>(null);
  const [loading, setLoading]   = useState(true);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [snap, rep] = await Promise.all([
        api.getBtcSnapshot(),
        api.getBtcLatestReport(),
      ]);
      setSnapshot(snap);
      setReport(rep);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const TrendIcon = ({ trend }: { trend: string | null }) => {
    if (trend === "bullish") return <TrendingUp size={14} className="text-[var(--accent-green)]" />;
    if (trend === "bearish") return <TrendingDown size={14} className="text-[var(--accent-red)]" />;
    return <Minus size={14} className="text-[var(--text-muted)]" />;
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] p-4 md:p-6 space-y-4">

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <ArrowLeft size={18} />
          </Link>
          <div>
            <h1 className="text-lg font-bold text-[var(--text-primary)]">
              Bitcoin
            </h1>
            <p className="text-xs text-[var(--text-muted)]">
              Derivate-Daten · CoinGlass + yfinance
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)]
                       px-3 py-1.5 text-xs text-[var(--text-secondary)]
                       hover:bg-[var(--bg-tertiary)] disabled:opacity-40">
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Aktualisieren
          </button>
          <button
            onClick={async () => {
              setGenerating(true);
              try {
                await api.generateBtcReport();
                await load();
              } catch (e) { console.error(e); }
              finally { setGenerating(false); }
            }}
            disabled={generating}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--accent-blue)]
                       px-3 py-1.5 text-xs text-white hover:opacity-90 disabled:opacity-40">
            {generating
              ? <RefreshCw size={12} className="animate-spin" />
              : <Brain size={12} />}
            KI-Lagebericht
          </button>
        </div>
      </div>

      {/* ── AI Chat (immer zuerst) ──────────────────────────── */}
      <TickerChatBlock 
        ticker="BTC" 
        contextSnapshot={{ 
          ticker: "BTC", 
          companyName: "Bitcoin", 
          assetType: "cryptocurrency" 
        }} 
      />

      {/* Metriken */}
      {snapshot && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            {
              label: "Bitcoin Kurs",
              value: `$${fmt(snapshot.price.price, 0)}`,
              sub: `7T: ${snapshot.price.change_7d_pct != null ? (snapshot.price.change_7d_pct >= 0 ? "+" : "") + snapshot.price.change_7d_pct.toFixed(1) + "%" : "—"}`,
              color: (snapshot.price.change_7d_pct || 0) >= 0
                ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]",
              icon: <TrendIcon trend={snapshot.price.trend} />,
            },
            {
              label: "Open Interest",
              value: snapshot.open_interest?.total_oi_usd
                ? `$${(snapshot.open_interest.total_oi_usd / 1e9).toFixed(1)}B` 
                : "—",
              sub: snapshot.open_interest?.change_24h_pct != null
                ? `24h: ${snapshot.open_interest.change_24h_pct >= 0 ? "+" : ""}${snapshot.open_interest.change_24h_pct.toFixed(1)}%` 
                : "—",
              color: "text-[var(--text-primary)]",
            },
            {
              label: "Funding Rate",
              value: snapshot.funding_rate?.avg_funding_rate_pct != null
                ? `${snapshot.funding_rate.avg_funding_rate_pct > 0 ? "+" : ""}${snapshot.funding_rate.avg_funding_rate_pct.toFixed(4)}%` 
                : "—",
              sub: snapshot.funding_rate?.interpretation || "—",
              color: (snapshot.funding_rate?.avg_funding_rate_pct || 0) > 0.05
                ? "text-[var(--accent-red)]"
                : (snapshot.funding_rate?.avg_funding_rate_pct || 0) < -0.05
                  ? "text-[var(--accent-green)]"
                  : "text-[var(--text-primary)]",
            },
            {
              label: "Long / Short",
              value: snapshot.long_short
                ? `${snapshot.long_short.long_pct?.toFixed(0)}% / ${snapshot.long_short.short_pct?.toFixed(0)}%` 
                : "—",
              sub: snapshot.long_short
                ? ((snapshot.long_short.long_pct || 50) > 55
                    ? "Retail bullish"
                    : (snapshot.long_short.long_pct || 50) < 45
                      ? "Retail bearish"
                      : "Neutral")
                : "—",
              color: "text-[var(--text-primary)]",
            },
          ].map(m => (
            <div key={m.label} className="card p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
                  {m.label}
                </p>
                {m.icon && m.icon}
              </div>
              <p className={`text-xl font-bold font-mono ${m.color}`}>{m.value}</p>
              <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{m.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* DXY Kontext */}
      {snapshot?.dxy && (
        <div className="card p-3 flex items-center gap-3">
          <Activity size={14} className="text-[var(--text-muted)]" />
          <div>
            <span className="text-xs text-[var(--text-muted)]">DXY: </span>
            <span className="text-sm font-mono font-bold text-[var(--text-primary)]">
              {snapshot.dxy.toFixed(2)}
            </span>
            <span className="text-xs text-[var(--text-muted)] ml-2">
              {snapshot.dxy > 104
                ? "Stark — BTC Gegenwind"
                : snapshot.dxy < 100
                  ? "Schwach — BTC Rückenwind"
                  : "Neutral"}
            </span>
          </div>
          <span className="ml-auto text-[10px] text-[var(--text-muted)]">
            Stand: {snapshot.fetched_at
              ? new Date(snapshot.fetched_at).toLocaleTimeString("de-DE",
                  { hour: "2-digit", minute: "2-digit" })
              : "—"} Uhr
          </span>
        </div>
      )}

      {/* KI-Lagebericht */}
      {report?.report && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={13} className="text-[var(--accent-blue)]" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em]
                         text-[var(--accent-blue)]">
              KI-Lagebericht
            </p>
            {report.generated_at && (
              <span className="ml-auto text-[10px] text-[var(--text-muted)]">
                {report.date} · {new Date(report.generated_at).toLocaleTimeString("de-DE",
                  { hour: "2-digit", minute: "2-digit" })} Uhr
              </span>
            )}
          </div>
          <div className="whitespace-pre-wrap text-sm text-[var(--text-primary)] leading-relaxed">
            {report.report}
          </div>
        </div>
      )}

      {!loading && !report?.report && (
        <div className="card p-12 text-center">
          <Brain size={24} className="mx-auto mb-3 text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">
            Kein BTC-Lagebericht vorhanden.
          </p>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Klicke "KI-Lagebericht" um einen zu generieren.
          </p>
        </div>
      )}

    </div>
  );
}
