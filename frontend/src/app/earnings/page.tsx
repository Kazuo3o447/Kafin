"use client";

import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";
import { Loader2, Sunrise, Moon, Clock, TrendingUp, TrendingDown, ExternalLink } from "lucide-react";
import Link from "next/link";

type EarningsEntry = {
  ticker: string;
  report_date: string;
  report_timing: string | null;
  eps_consensus: number | null;
  revenue_consensus: number | null;
  is_watchlist: boolean;
  cross_signal_for: string[];
  is_today: boolean;
  days_until: number | null;
  pre_earnings_sentiment?: {
    avg: number;
    label: string;
    trend: string;
    has_material: boolean;
    count: number;
  } | null;
};

type RadarData = {
  entries: EarningsEntry[];
  total: number;
  from_date: string;
  to_date: string;
  watchlist_count: number;
  today_count: number;
};

type SnapshotData = {
  ticker: string;
  price: number | null;
  rsi: number | null;
  trend: string | null;
  sma_50: number | null;
  sma_200: number | null;
  next_earnings_date: string | null;
  report_timing: string | null;
  eps_consensus: number | null;
  revenue_consensus: number | null;
  last_eps_surprise_pct: number | null;
  last_beat: boolean | null;
  avg_surprise_pct: number | null;
  beats_of_8: number | null;
  short_interest_pct: number | null;
  iv_approx: number | null;
  earnings_countdown_days: number | null;
  earnings_today: boolean;
  is_on_watchlist: boolean;
  error?: string;
};

export default function EarningsRadarPage() {
  const [radarData, setRadarData] = useState<RadarData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "watchlist" | "today">("all");
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  const [generatingReport, setGeneratingReport] = useState<string | null>(null);
  const [reportResult, setReportResult] = useState<string | null>(null);
  const [addedToWatchlist, setAddedToWatchlist] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api.getEarningsRadar(14)
      .then(setRadarData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (expandedTicker && snapshot?.ticker !== expandedTicker) {
      setLoadingSnapshot(true);
      api.getQuickSnapshot(expandedTicker)
        .then(setSnapshot)
        .catch(console.error)
        .finally(() => setLoadingSnapshot(false));
    }
  }, [expandedTicker, snapshot?.ticker]);

  const filtered = useMemo(() => {
    if (!radarData) return [];
    switch (filter) {
      case "watchlist": return radarData.entries.filter(e => e.is_watchlist);
      case "today": return radarData.entries.filter(e => e.is_today);
      default: return radarData.entries;
    }
  }, [radarData, filter]);

  const groupedByDay = useMemo(() => {
    const groups: { date: string, label: string, entries: EarningsEntry[] }[] = [];
    filtered.forEach(entry => {
      if (!entry.report_date) return;
      let label = "";
      if (entry.is_today) {
        label = "Heute";
      } else if (entry.days_until === 1) {
        label = "Morgen";
      } else if (entry.days_until !== null && entry.days_until >= 2 && entry.days_until <= 7) {
        const d = new Date(entry.report_date);
        label = `${["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"][d.getDay()]}, ${d.getDate()}.${d.getMonth() + 1}. (Diese Woche)`;
      } else if (entry.days_until !== null && entry.days_until > 7) {
         const d = new Date(entry.report_date);
         label = `${["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"][d.getDay()]}, ${d.getDate()}.${d.getMonth() + 1}. (Nächste Woche)`;
      } else {
        label = entry.report_date;
      }

      let group = groups.find(g => g.date === entry.report_date);
      if (!group) {
        group = { date: entry.report_date, label, entries: [] };
        groups.push(group);
      }
      group.entries.push(entry);
    });
    return groups;
  }, [filtered]);

  async function handleGenerateReport(ticker: string) {
    setGeneratingReport(ticker);
    setReportResult(null);
    try {
      const result = await api.generateAuditReport(ticker);
      setReportResult(result.report || result.message || "Report generiert.");
      setExpandedTicker(ticker);
    } catch (err) {
      setReportResult("Fehler beim Generieren des Reports.");
    } finally {
      setGeneratingReport(null);
    }
  }

  async function handleAddToWatchlist(ticker: string) {
    try {
      await api.addTicker({
        ticker,
        company_name: ticker,
        sector: "Unknown",
        notes: "Manuell hinzugefügt via Earnings-Radar"
      });
      setAddedToWatchlist(prev => ({ ...prev, [ticker]: true }));
    } catch (err) {
      console.error("Watchlist add error:", err);
    }
  }

  const renderTimingIcon = (timing: string | null) => {
    if (timing === "pre_market") return <Sunrise size={14} className="text-amber-400" />;
    if (timing === "after_hours") return <Moon size={14} className="text-indigo-400" />;
    return <Clock size={14} className="text-[var(--text-muted)]" />;
  };

  if (loading) {
    return (
      <div className="space-y-8 p-8">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Earnings-Radar</h1>
          <div className="h-4 w-64 bg-[var(--bg-tertiary)] animate-pulse rounded mt-2"></div>
        </div>
        <div className="space-y-4">
           {[...Array(6)].map((_, i) => (
             <div key={i} className="h-16 w-full bg-[var(--bg-tertiary)] animate-pulse rounded-xl" style={{ opacity: 1 - i * 0.1 }}></div>
           ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-8 pb-32">
      <div>
        <h1 className="text-4xl font-bold text-[var(--text-primary)] flex items-center gap-3">
          📅 Earnings-Radar
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">
          Nächste 14 Tage · {radarData?.total || 0} Earnings · <span className="text-amber-500 font-semibold">{radarData?.today_count || 0} heute</span>
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setFilter("all")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            filter === "all" ? "bg-[var(--accent-blue)] text-white shadow-md" : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Alle ({radarData?.total || 0})
        </button>
        <button
          onClick={() => setFilter("watchlist")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            filter === "watchlist" ? "bg-[var(--accent-blue)] text-white shadow-md" : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Watchlist ({radarData?.watchlist_count || 0})
        </button>
        <button
          onClick={() => setFilter("today")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            filter === "today" ? "bg-[var(--accent-blue)] text-white shadow-md" : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Heute ({radarData?.today_count || 0})
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="card p-12 text-center text-[var(--text-muted)]">
          Keine Earnings in diesem Zeitraum für den gewählten Filter.
        </div>
      ) : (
        <div className="space-y-8">
          {groupedByDay.map((group) => (
            <div key={group.date} className="space-y-3">
              <h2 className={`text-sm font-bold uppercase tracking-wide px-1 ${
                 group.label === "Heute" ? "text-amber-500" : "text-[var(--text-muted)]"
              }`}>
                ── {group.label} ─────────────────────────────────────────
              </h2>
              <div className="space-y-2">
                {group.entries.map((entry) => {
                  const isExpanded = expandedTicker === entry.ticker;
                  const isWl = entry.is_watchlist || addedToWatchlist[entry.ticker];
                  
                  return (
                    <div key={entry.ticker} className={`card overflow-hidden transition-all ${entry.is_today ? 'border-l-4 border-l-amber-500' : ''}`}>
                      <div className="flex items-center justify-between p-4">
                        <div className="flex items-center gap-4">
                          <div className={`px-2.5 py-1 rounded text-sm font-bold tracking-wider ${
                            isWl ? 'bg-[var(--accent-green)] bg-opacity-20 text-[var(--accent-green)]' :
                            entry.cross_signal_for.length > 0 ? 'bg-[var(--accent-blue)] bg-opacity-20 text-[var(--accent-blue)]' :
                            'bg-[var(--bg-tertiary)] text-[var(--text-primary)]'
                          }`}>
                            {entry.ticker}
                          </div>
                          
                          {/* Pre-Earnings Sentiment */}
                          {entry.pre_earnings_sentiment && (
                            <div className="flex items-center gap-1 px-2 py-1 rounded bg-[var(--bg-tertiary)]">
                              <div className={`text-xs font-mono font-semibold ${
                                entry.pre_earnings_sentiment.avg > 0.15 ? "text-[var(--accent-green)]"
                                : entry.pre_earnings_sentiment.avg < -0.15 ? "text-[var(--accent-red)]"
                                : "text-[var(--text-muted)]"
                              }`}>
                                {entry.pre_earnings_sentiment.avg >= 0 ? "+" : ""}{entry.pre_earnings_sentiment.avg.toFixed(2)}
                              </div>
                              <div className={`text-[9px] ${
                                entry.pre_earnings_sentiment.trend === "improving" ? "text-[var(--accent-green)]"
                                : entry.pre_earnings_sentiment.trend === "deteriorating" ? "text-[var(--accent-red)]"
                                : "text-[var(--text-muted)]"
                              }`}>
                                {entry.pre_earnings_sentiment.trend === "improving" ? "↑"
                                 : entry.pre_earnings_sentiment.trend === "deteriorating" ? "↓"
                                 : "→"}
                              </div>
                              {entry.pre_earnings_sentiment.has_material && (
                                <div className="w-2 h-2 rounded-full bg-[var(--accent-red)]" title="Material Event erkannt" />
                              )}
                            </div>
                          )}
                          
                          <div className="flex items-center gap-1 text-[var(--text-muted)] tooltip-trigger" title={entry.report_timing === "pre_market" ? "Vor Börseneröffnung" : entry.report_timing === "after_hours" ? "Nach Börsenschluss" : "Unbekannt"}>
                             {renderTimingIcon(entry.report_timing)}
                          </div>
                          
                          <div className="text-sm text-[var(--text-secondary)] w-24">
                            EPS: <span className="text-[var(--text-primary)] font-mono">{entry.eps_consensus != null ? `$${entry.eps_consensus.toFixed(2)}` : '—'}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          {entry.cross_signal_for.length > 0 && !isWl && (
                            <span className="text-xs font-medium text-amber-500 hidden md:inline-block mr-2">
                              Relevant für: {entry.cross_signal_for.join(', ')}
                            </span>
                          )}
                          
                          {isWl ? (
                            <span className="text-xs font-semibold text-[var(--accent-green)] bg-[var(--accent-green)] bg-opacity-10 px-2 py-1 rounded hidden md:inline-block">✓ Watchlist</span>
                          ) : (
                            <button 
                              onClick={() => handleAddToWatchlist(entry.ticker)}
                              className="text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] px-2 py-1 rounded bg-[var(--bg-tertiary)] hidden md:inline-block"
                            >
                              + Watchlist
                            </button>
                          )}

                          <button 
                            onClick={() => handleGenerateReport(entry.ticker)}
                            disabled={generatingReport !== null}
                            className="text-xs font-medium text-[var(--text-primary)] px-3 py-1.5 rounded bg-[var(--bg-tertiary)] hover:bg-[var(--border)] transition disabled:opacity-50"
                          >
                            Audit-Report
                          </button>
                          
                          <button 
                            onClick={() => setExpandedTicker(isExpanded ? null : entry.ticker)}
                            className={`text-xs font-semibold px-3 py-1.5 rounded transition ${
                              isExpanded ? "bg-[var(--text-primary)] text-[var(--bg-primary)]" : "bg-[var(--accent-blue)] bg-opacity-10 text-[var(--accent-blue)] hover:bg-opacity-20"
                            }`}
                          >
                            {isExpanded ? "Schließen" : "Schnell-Analyse"}
                          </button>
                        </div>
                      </div>

                      {/* Snapshot Panel */}
                      {isExpanded && (
                        <div className="bg-[var(--bg-tertiary)] border-t border-[var(--border)] p-5">
                          {loadingSnapshot ? (
                            <div className="flex items-center justify-center py-8 text-[var(--text-muted)] gap-2 text-sm">
                              <Loader2 className="animate-spin" size={16} /> Lade Snapshot für {entry.ticker}...
                            </div>
                          ) : snapshot?.error ? (
                            <div className="text-rose-400 text-sm py-4 text-center">{snapshot.error}</div>
                          ) : snapshot ? (
                            <div className="space-y-5">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Links: Technik */}
                                <div className="space-y-3">
                                  <h4 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Technisches Setup</h4>
                                  <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div className="text-[var(--text-secondary)]">Preis:</div>
                                    <div className={`font-mono font-bold ${(snapshot.rsi || 50) > 50 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                      ${snapshot.price?.toFixed(2) ?? '—'}
                                    </div>
                                    
                                    <div className="text-[var(--text-secondary)]">RSI (14):</div>
                                    <div className="font-mono flex items-center gap-1 text-[var(--text-primary)]">
                                      {snapshot.rsi?.toFixed(1) ?? '—'} 
                                      {snapshot.rsi && snapshot.rsi > 70 ? <TrendingUp size={14} className="text-rose-400"/> : snapshot.rsi && snapshot.rsi < 30 ? <TrendingDown size={14} className="text-emerald-400"/> : null}
                                    </div>
                                    
                                    <div className="text-[var(--text-secondary)]">Trend:</div>
                                    <div className="capitalize text-[var(--text-primary)]">{snapshot.trend ?? '—'}</div>
                                    
                                    <div className="text-[var(--text-secondary)]">SMA 50/200:</div>
                                    <div className="font-mono text-xs text-[var(--text-muted)] flex items-center gap-2">
                                       <span className={snapshot.price && snapshot.sma_50 && snapshot.price > snapshot.sma_50 ? "text-emerald-400" : "text-rose-400"}>50: {snapshot.sma_50 ?? '-'}</span>
                                       <span className={snapshot.price && snapshot.sma_200 && snapshot.price > snapshot.sma_200 ? "text-emerald-400" : "text-rose-400"}>200: {snapshot.sma_200 ?? '-'}</span>
                                    </div>
                                  </div>
                                </div>
                                
                                {/* Rechts: Earnings */}
                                <div className="space-y-3">
                                  <h4 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Earnings Context</h4>
                                  <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div className="text-[var(--text-secondary)]">Termin:</div>
                                    <div className="text-[var(--text-primary)]">{snapshot.next_earnings_date} <span className="text-[var(--text-muted)]">({snapshot.report_timing === 'pre_market' ? 'Pre' : snapshot.report_timing === 'after_hours' ? 'AH' : 'Unbekannt'})</span></div>
                                    
                                    <div className="text-[var(--text-secondary)]">Konsens:</div>
                                    <div className="font-mono text-[var(--text-primary)]">
                                      EPS ${snapshot.eps_consensus?.toFixed(2) ?? '-'} | Rev {snapshot.revenue_consensus ? snapshot.revenue_consensus > 1e9 ? `${(snapshot.revenue_consensus/1e9).toFixed(2)}B` : `${(snapshot.revenue_consensus/1e6).toFixed(0)}M` : '-'}
                                    </div>
                                    
                                    <div className="text-[var(--text-secondary)]">Letztes Quartal:</div>
                                    <div className={`font-mono font-bold ${snapshot.last_beat === true ? 'text-emerald-400' : snapshot.last_beat === false ? 'text-rose-400' : 'text-[var(--text-primary)]'}`}>
                                      {snapshot.last_eps_surprise_pct != null ? `${snapshot.last_eps_surprise_pct > 0 ? '+' : ''}${snapshot.last_eps_surprise_pct.toFixed(1)}% Surprise` : '—'}
                                    </div>
                                    
                                    <div className="text-[var(--text-secondary)]">Historie (8Q):</div>
                                    <div className="text-[var(--text-primary)]">
                                      {snapshot.beats_of_8 ?? '-'}/8 Beats <span className="text-[var(--text-muted)] text-xs">(Ø {snapshot.avg_surprise_pct != null ? `${snapshot.avg_surprise_pct>0?'+':''}${snapshot.avg_surprise_pct}%` : '-'})</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-6 border-t border-[var(--border)] pt-3 text-xs text-[var(--text-muted)]">
                                <div>Short Interest: <span className="text-[var(--text-primary)] font-mono ml-1">{snapshot.short_interest_pct?.toFixed(1) ?? '—'}%</span></div>
                                <div>IV (Approx): <span className="text-[var(--text-primary)] font-mono ml-1">{snapshot.iv_approx?.toFixed(1) ?? '—'}%</span></div>
                                
                                <div className="ml-auto flex items-center gap-2">
                                  {!isWl && (
                                     <button onClick={() => handleAddToWatchlist(entry.ticker)} className="hover:text-[var(--text-primary)] transition">+ Zur Watchlist</button>
                                  )}
                                  {isWl && <span className="text-emerald-400">✓ Auf Watchlist</span>}
                                  <Link href={`/research/${entry.ticker}`} target="_blank" className="flex items-center gap-1 hover:text-[var(--text-primary)] transition ml-2">
                                    Detailseite <ExternalLink size={12}/>
                                  </Link>
                                </div>
                              </div>
                            </div>
                          ) : null}
                          
                          {generatingReport === entry.ticker && (
                            <div className="mt-4 p-4 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] flex items-center justify-center gap-3 text-sm text-[var(--text-secondary)]">
                              <Loader2 className="animate-spin text-[var(--accent-blue)]" size={16} /> Audit-Report wird generiert... (30-60 Sekunden)
                            </div>
                          )}
                          
                          {reportResult && generatingReport !== entry.ticker && (
                            <div className="mt-4 p-4 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                              <h4 className="text-xs font-bold text-[var(--text-muted)] mb-2">KI Audit-Report</h4>
                              <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                                {reportResult}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
