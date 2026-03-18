"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Loader2, ExternalLink } from "lucide-react";

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
  error?: string;
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loading, setLoading] = useState(false);
  const [addedToWatchlist, setAddedToWatchlist] = useState(false);
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
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setSnapshot(null);
      setReportText(null);
      setAddedToWatchlist(false);
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
    } catch (err) {
      console.error("Watchlist add error:", err);
    }
  }

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50" onClick={() => setOpen(false)} />
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-xl z-50 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[70vh]">
        <div className="p-4 border-b border-[var(--border)] flex items-center gap-3">
          <span className="text-[var(--text-muted)]">🔍</span>
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
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-3xl font-bold font-mono text-[var(--text-primary)]">{snapshot.ticker}</h2>
                    <p className="text-xl text-[var(--text-secondary)]">${snapshot.price?.toFixed(2) ?? "—"}</p>
                  </div>
                  {snapshot.is_on_watchlist ? (
                    <span className="bg-[var(--accent-green)] bg-opacity-20 text-[var(--accent-green)] text-xs font-bold px-3 py-1 rounded-full">✓ Watchlist</span>
                  ) : (
                    <span className="bg-[var(--bg-tertiary)] text-[var(--text-muted)] text-xs px-3 py-1 rounded-full">Nicht auf Watchlist</span>
                  )}
                </div>

                {snapshot.next_earnings_date && (
                  <div className={`p-4 rounded-xl border ${snapshot.earnings_today ? 'bg-amber-500/10 border-amber-500/30' : snapshot.earnings_this_week ? 'bg-blue-500/10 border-blue-500/30' : 'bg-[var(--bg-primary)] border-[var(--border)]'}`}>
                    <div className={`font-bold ${snapshot.earnings_today ? 'text-amber-500' : snapshot.earnings_this_week ? 'text-blue-400' : 'text-[var(--text-primary)]'}`}>
                      {snapshot.earnings_today ? '⚡ Meldet HEUTE' : snapshot.earnings_this_week ? `📅 Meldet in ${snapshot.earnings_countdown_days} Tagen` : `📅 Nächste Earnings: ${snapshot.next_earnings_date}`}
                      {' — '}
                      {snapshot.report_timing === 'pre_market' ? 'Pre-Market 🌅' : snapshot.report_timing === 'after_hours' ? 'After-Hours 🌙' : ''}
                    </div>
                    <div className="mt-2 text-sm text-[var(--text-secondary)] font-mono">
                      EPS Konsens: ${snapshot.eps_consensus?.toFixed(2) ?? '—'} | Revenue: {snapshot.revenue_consensus ? snapshot.revenue_consensus > 1e9 ? `${(snapshot.revenue_consensus/1e9).toFixed(2)}B` : `${(snapshot.revenue_consensus/1e6).toFixed(0)}M` : '—'}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="card p-3">
                    <div className="text-xs text-[var(--text-muted)] mb-1">RSI / Trend</div>
                    <div className="font-mono text-[var(--text-primary)]">{snapshot.rsi?.toFixed(1) ?? '—'} | {snapshot.trend ?? '—'}</div>
                  </div>
                  <div className="card p-3">
                    <div className="text-xs text-[var(--text-muted)] mb-1">Surprise Historie (8Q)</div>
                    <div className="font-mono text-[var(--text-primary)]">
                      Letzter: <span className={snapshot.last_beat === true ? 'text-emerald-400' : snapshot.last_beat === false ? 'text-rose-400' : ''}>{snapshot.last_eps_surprise_pct != null ? `${snapshot.last_eps_surprise_pct>0?'+':''}${snapshot.last_eps_surprise_pct}%` : '—'}</span>
                      <br/>Ø: {snapshot.avg_surprise_pct != null ? `${snapshot.avg_surprise_pct>0?'+':''}${snapshot.avg_surprise_pct}%` : '—'}
                    </div>
                  </div>
                  <div className="card p-3">
                    <div className="text-xs text-[var(--text-muted)] mb-1">Market Data</div>
                    <div className="font-mono text-[var(--text-primary)]">
                      SI: {snapshot.short_interest_pct?.toFixed(1) ?? '—'}%<br/>
                      IV: {snapshot.iv_approx?.toFixed(1) ?? '—'}%
                    </div>
                  </div>
                  <div className="card p-3">
                    <div className="text-xs text-[var(--text-muted)] mb-1">Consistency</div>
                    <div className="font-mono text-[var(--text-primary)]">{snapshot.beats_of_8 ?? '—'}/8 Quartale geschlagen</div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button 
                    onClick={handleGenerateReport}
                    disabled={generatingReport}
                    className="flex-1 bg-[var(--accent-blue)] text-white font-semibold py-2 rounded-lg hover:opacity-90 transition disabled:opacity-50"
                  >
                    🤖 Audit-Report
                  </button>
                  
                  {!snapshot.is_on_watchlist && !addedToWatchlist && (
                    <button 
                      onClick={handleAddToWatchlist}
                      className="flex-1 bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border)] font-semibold py-2 rounded-lg hover:bg-[var(--border)] transition"
                    >
                      + Zur Watchlist
                    </button>
                  )}
                  
                  {(snapshot.is_on_watchlist || addedToWatchlist) && (
                    <button disabled className="flex-1 bg-[var(--accent-green)] bg-opacity-20 text-[var(--accent-green)] font-semibold py-2 rounded-lg cursor-default border border-[var(--accent-green)] border-opacity-30">
                      ✓ Auf Watchlist
                    </button>
                  )}
                  
                  <a 
                    href={`/watchlist/${snapshot.ticker}`} 
                    target="_blank" 
                    rel="noreferrer"
                    className="flex-1 flex items-center justify-center gap-2 bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border)] font-semibold py-2 rounded-lg hover:bg-[var(--border)] transition"
                  >
                    Details <ExternalLink size={16} />
                  </a>
                </div>

                {generatingReport && (
                  <div className="p-4 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] flex items-center justify-center gap-3 text-sm text-[var(--text-secondary)]">
                    <Loader2 className="animate-spin text-[var(--accent-blue)]" size={16} /> Audit-Report wird generiert... (30-60 Sekunden)
                  </div>
                )}
                
                {reportText && !generatingReport && (
                  <div className="mt-4 p-4 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                    <h4 className="text-xs font-bold text-[var(--text-muted)] mb-2">KI Audit-Report</h4>
                    <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                      {reportText}
                    </div>
                    <div className="mt-3 text-center">
                      <a href="/reports" className="text-xs text-[var(--accent-blue)] hover:underline">Volltext auf Reports-Seite ansehen</a>
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
