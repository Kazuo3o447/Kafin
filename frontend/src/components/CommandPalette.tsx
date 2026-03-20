"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Loader2, ExternalLink, Sparkles, TrendingUp, BookmarkPlus, BookmarkMinus, Clock } from "lucide-react";

type SnapshotData = {
  ticker: string;
  price: number | null;
  rsi: number | null;
  trend: string | null;
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
  earnings_this_week: boolean;
  is_on_watchlist: boolean;
  latest_audit?: {
    report_date: string;
    recommendation: string;
    opportunity_score: number;
    torpedo_score: number;
  } | null;
  error?: string;
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loading, setLoading] = useState(false);
  const [addedToWatchlist, setAddedToWatchlist] = useState(false);
  const [removedFromWatchlist, setRemovedFromWatchlist] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [reportText, setReportText] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    }

    // Custom Event für den Sidebar-Button (funktioniert auf Windows + Mac)
    function handleOpenPalette() {
      setOpen(true);
    }

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("open-command-palette", handleOpenPalette);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("open-command-palette", handleOpenPalette);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setSnapshot(null);
      setReportText(null);
      setAddedToWatchlist(false);
      setRemovedFromWatchlist(false);
    }
  }, [open]);

  useEffect(() => {
    if (!query || query.length < 1) {
      setSnapshot(null);
      return;
    }

    const ticker = query.toUpperCase().trim();
    if (!/^[A-Z]{1,5}$/.test(ticker)) {
      setSnapshot(null);
      return;
    }

    const timeout = setTimeout(async () => {
      setLoading(true);
      setSnapshot(null);
      setReportText(null);
      try {
        const data = await api.getQuickSnapshot(ticker);
        setSnapshot(data);
      } catch (err) {
        setSnapshot({ ticker, error: "Ticker nicht gefunden", price: null } as any);
      } finally {
        setLoading(false);
      }
    }, 600);

    return () => clearTimeout(timeout);
  }, [query]);

  async function handleGenerateReport() {
    if (!snapshot) return;
    setGeneratingReport(true);
    setReportText(null);
    try {
      const result = await api.generateAuditReport(snapshot.ticker);
      setReportText(result.report || result.message || "Report generiert.");
    } catch {
      setReportText("Report-Generierung fehlgeschlagen.");
    } finally {
      setGeneratingReport(false);
    }
  }

  async function handleAddToWatchlist() {
    if (!snapshot) return;
    try {
      await api.addTicker({
        ticker: snapshot.ticker,
        company_name: snapshot.ticker,
        sector: "Unknown",
        notes: "Manuell hinzugefügt via Schnellsuche (Cmd+K)",
      });
      setAddedToWatchlist(true);
      setRemovedFromWatchlist(false);
    } catch (err) {
      console.error("Watchlist add error:", err);
    }
  }

  async function handleRemoveFromWatchlist() {
    if (!snapshot) return;
    try {
      await api.removeTicker(snapshot.ticker);
      setRemovedFromWatchlist(true);
      setAddedToWatchlist(false);
    } catch (err) {
      console.error("Watchlist remove error:", err);
    }
  }

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50" onClick={() => setOpen(false)} />
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-xl z-50 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[70vh]">
        <div className="p-4 border-b border-[var(--border)] flex items-center gap-3">
          <Sparkles size={16} className="text-[var(--text-muted)]" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ticker eingeben — z.B. MU, NVDA, AAPL"
            className="flex-1 bg-transparent text-xl font-mono text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] placeholder:font-sans"
            autoComplete="off"
            spellCheck={false}
          />
          <button onClick={() => setOpen(false)} className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] bg-[var(--bg-tertiary)] px-2 py-1 rounded">Esc</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {loading && query.length > 0 && (
            <div className="flex items-center justify-center py-12 gap-3 text-[var(--text-muted)]">
              <Loader2 className="animate-spin" size={18} /> Lade Daten für {query.toUpperCase()}...
            </div>
          )}

          {!loading && snapshot && (
            snapshot.error ? (
              <div className="text-center py-8 text-rose-400">
                Ticker '{query.toUpperCase()}' nicht gefunden oder keine Daten verfügbar.
              </div>
            ) : (
              <div className="space-y-6">
                {/* Header Section */}
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
                  <div>
                    <h2 className="text-4xl font-bold font-mono text-[var(--text-primary)]">{snapshot.ticker}</h2>
                    {snapshot.price !== null && snapshot.price !== undefined ? (
                      <p className="text-2xl font-mono text-[var(--text-primary)] mt-1">${snapshot.price.toFixed(2)}</p>
                    ) : (
                      <p className="text-sm text-[var(--text-muted)] mt-1">Kursdaten nicht verfügbar</p>
                    )}
                  </div>
                  {(snapshot.is_on_watchlist || addedToWatchlist) && !removedFromWatchlist ? (
                    <span className="bg-[var(--accent-green)]/20 border border-[var(--accent-green)]/30 text-[var(--accent-green)] text-xs font-bold px-4 py-2 rounded-full flex items-center gap-2">
                      <BookmarkMinus size={14} /> Auf Watchlist
                    </span>
                  ) : (
                    <span className="bg-[var(--bg-tertiary)] border border-[var(--border)] text-[var(--text-muted)] text-xs px-4 py-2 rounded-full flex items-center gap-2">
                      <BookmarkPlus size={14} /> Nicht beobachtet
                    </span>
                  )}
                </div>

                {/* KI Audit Historie */}
                <div className="p-4 rounded-xl bg-[var(--bg-tertiary)] border border-[var(--border)]">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles size={16} className="text-[var(--accent-blue)]" />
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">KI Audit Status</h3>
                  </div>
                  {snapshot.latest_audit ? (
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <div className="text-xs text-[var(--text-muted)] flex items-center gap-1"><Clock size={12}/> Letztes Update</div>
                        <div className="text-sm font-mono text-[var(--text-primary)] mt-1">
                          {new Date(snapshot.latest_audit.report_date).toLocaleDateString('de-DE')}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--text-muted)]">Empfehlung</div>
                        <div className={`text-sm font-bold mt-1 ${snapshot.latest_audit.recommendation.toUpperCase() === 'BUY' ? 'text-[var(--accent-green)]' : snapshot.latest_audit.recommendation.toUpperCase() === 'SELL' ? 'text-[var(--accent-red)]' : 'text-amber-400'}`}>
                          {snapshot.latest_audit.recommendation.toUpperCase()}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--text-muted)]">Opp / Torp Score</div>
                        <div className="text-sm font-mono text-[var(--text-primary)] mt-1">
                          <span className="text-[var(--accent-blue)]">{snapshot.latest_audit.opportunity_score}</span> / <span className="text-rose-400">{snapshot.latest_audit.torpedo_score}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--text-muted)]">Bisher kein Audit-Report vorhanden. Generiere einen Report für fundamentale und psychologische Insights.</p>
                  )}
                </div>

                {/* Marktdaten Mini-Dashboard (Aus bestehenden Daten) */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                    <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] mb-1">RSI & Trend</div>
                    <div className="font-mono text-sm text-[var(--text-primary)]">{snapshot.rsi?.toFixed(1) ?? '—'} <span className="text-[var(--text-secondary)] text-xs">({snapshot.trend ?? '—'})</span></div>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                    <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] mb-1 flex items-center gap-1">Implizite Vola</div>
                    <div className="font-mono text-sm text-[var(--text-primary)]">{snapshot.iv_approx ? `${snapshot.iv_approx.toFixed(1)}%` : '—'}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                    <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] mb-1">Short Interest</div>
                    <div className="font-mono text-sm text-[var(--text-primary)]">{snapshot.short_interest_pct ? `${snapshot.short_interest_pct.toFixed(1)}%` : '—'}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                    <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] mb-1">Surprise Ø</div>
                    <div className="font-mono text-sm text-[var(--text-primary)]">{snapshot.avg_surprise_pct != null ? `${snapshot.avg_surprise_pct>0?'+':''}${snapshot.avg_surprise_pct}%` : '—'}</div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button 
                    onClick={handleGenerateReport}
                    disabled={generatingReport}
                    className="flex-1 min-w-[180px] bg-[var(--accent-blue)] text-white font-semibold py-2.5 rounded-lg hover:opacity-90 transition disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-[var(--accent-blue)]/20"
                  >
                    {generatingReport ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />} 
                    {snapshot.latest_audit ? "Audit aktualisieren" : "Deep-Dive Audit starten"}
                  </button>
                  
                  {(!snapshot.is_on_watchlist && !addedToWatchlist) || removedFromWatchlist ? (
                    <button 
                      onClick={handleAddToWatchlist}
                      className="flex-1 min-w-[160px] bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border)] font-semibold py-2.5 rounded-lg hover:bg-[var(--border)] transition flex items-center justify-center gap-2"
                    >
                      <BookmarkPlus size={16} /> Zur Watchlist
                    </button>
                  ) : (
                    <button 
                      onClick={handleRemoveFromWatchlist}
                      className="flex-1 min-w-[160px] bg-rose-500/10 text-rose-400 border border-rose-500/30 font-semibold py-2.5 rounded-lg hover:bg-rose-500/20 transition flex items-center justify-center gap-2"
                    >
                      <BookmarkMinus size={16} /> Entfernen
                    </button>
                  )}
                  
                  <a 
                    href={`/research/${snapshot.ticker}`} 
                    target="_blank" 
                    rel="noreferrer"
                    className="flex-none flex items-center justify-center gap-2 bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border)] font-semibold px-4 py-2.5 rounded-lg hover:bg-[var(--border)] transition"
                  >
                    <TrendingUp size={16} /> Details
                  </a>
                </div>

                {/* Report Generation Feedback */}
                {generatingReport && (
                  <div className="p-4 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] flex items-center justify-center gap-3 text-sm text-[var(--text-secondary)]">
                    <Loader2 className="animate-spin text-[var(--accent-blue)]" size={16} /> Audit-Report wird tiefgehend analysiert und erstellt...
                  </div>
                )}
                
                {reportText && !generatingReport && (
                  <div className="mt-4 p-4 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                    <h4 className="text-xs font-bold text-[var(--text-muted)] mb-2 flex items-center gap-1"><Sparkles size={12}/> Frischer KI Audit-Report</h4>
                    <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                      {reportText}
                    </div>
                  </div>
                )}
              </div>
            )
          )}
        </div>
        
        <div className="p-2 text-center text-xs text-[var(--text-muted)] border-t border-[var(--border)] bg-[var(--bg-primary)]">
          Cmd+K schließen · Esc
        </div>
      </div>
    </>
  );
}
