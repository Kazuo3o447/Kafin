"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Plus, Trash2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { cachedFetch, cacheGet, cacheAge, cacheInvalidate } from "@/lib/clientCache";
import { CacheStatus } from "@/components/CacheStatus";

type WatchlistItem = {
  ticker: string;
  company_name?: string;
  sector?: string;
  notes?: string;
  opportunity_score?: number;
  torpedo_score?: number;
  price?: number;
  change_1d_pct?: number;
  recommendation?: string;
  web_prio?: number | null;
};

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTicker, setNewTicker] = useState({ ticker: "", company_name: "", sector: "", notes: "" });
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [dataAge, setDataAge] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && showAddModal) closeModal();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showAddModal]);

  useEffect(() => {
    loadWatchlist();
  }, []);

  const loadWatchlist = useCallback(async (invalidate = false) => {
    if (invalidate) {
      cacheInvalidate('watchlist:enriched');
      setRefreshing(true);
    }

    // Sofort gecachte Daten anzeigen (kein Ladescreen wenn Cache vorhanden)
    const cached = cacheGet<any>("watchlist:enriched");
    if (cached && !invalidate) {
      setWatchlist(cached.watchlist || []);
      setLoading(false);
      setFromCache(true);
      setDataAge(cacheAge("watchlist:enriched"));
      return; // Cache ist frisch genug — kein API-Call
    }

    if (!invalidate) setLoading(true);

    try {
      const { data, fromCache: isCached } = await cachedFetch("watchlist:enriched", () => api.getWatchlistEnriched(), 60);
      setWatchlist(data?.watchlist || []);
      setFromCache(isCached);
      setDataAge(cacheAge("watchlist:enriched"));
    } catch (error) {
      console.error("Watchlist fetch error", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  async function handleAddTicker() {
    const ticker = newTicker.ticker.trim().toUpperCase();

    // Validierung
    if (!ticker) {
      setAddError("Ticker darf nicht leer sein.");
      return;
    }
    if (!/^[A-Z]{1,5}$/.test(ticker)) {
      setAddError("Ungültiger Ticker — nur Buchstaben, max. 5 Zeichen (z.B. AAPL).");
      return;
    }

    setAddLoading(true);
    setAddError(null);

    try {
      await api.addTicker({
        ticker,
        company_name: newTicker.company_name || ticker,
        sector: newTicker.sector || "Unknown",
        notes: newTicker.notes || "",
      });
      // Erfolg
      closeModal();
      cacheInvalidate("watchlist:enriched");
      // Optimistic: Sofort den neuen Ticker hinzufügen
      setWatchlist(prev => [...prev, {
        ticker,
        company_name: newTicker.company_name || ticker,
        sector: newTicker.sector || "Unknown",
        notes: newTicker.notes || "",
        web_prio: null,
        price: undefined,
        change_1d_pct: undefined,
        opportunity_score: undefined,
        torpedo_score: undefined,
        recommendation: undefined,
      }]);
    } catch (err: any) {
      const msg = err?.message || "";
      if (msg.includes("409") || msg.toLowerCase().includes("duplicate")) {
        setAddError(`${ticker} ist bereits auf der Watchlist.`);
      } else if (msg.includes("422")) {
        setAddError("Ungültige Eingabe — prüfe den Ticker.");
      } else if (msg.includes("404")) {
        setAddError("API-Endpoint nicht erreichbar — Backend läuft?");
      } else {
        setAddError(`Fehler beim Hinzufügen: ${msg || "Unbekannter Fehler"}`);
      }
    } finally {
      setAddLoading(false);
    }
  }

  function closeModal() {
    setShowAddModal(false);
    setNewTicker({ ticker: "", company_name: "", sector: "", notes: "" });
    setAddError(null);
    setAddLoading(false);
  }

  async function handleRemoveTicker(ticker: string) {
    if (!confirm(`${ticker} wirklich entfernen?`)) return;
    try {
      await api.removeTicker(ticker);
      cacheInvalidate('watchlist:enriched');
      // Optimistic: Sofort den Ticker entfernen
      setWatchlist(prev => prev.filter(item => item.ticker !== ticker));
    } catch (error) {
      console.error("Remove ticker error", error);
    }
  }

  async function handleUpdateWebPrio(
    ticker: string,
    prio: number | null
  ) {
    try {
      await api.updateWebPrio(ticker, prio);
      cacheInvalidate("watchlist:list");
      cacheInvalidate("watchlist:enriched");
      // Optimistic Update wird direkt im onChange gemacht
    } catch (error) {
      console.error("Web Prio update error", error);
      // Bei Fehler: State zurücksetzen
      setWatchlist(prev => prev.map(w => 
        w.ticker === ticker 
          ? { ...w, web_prio: w.web_prio } // Originalwert behalten
          : w
      ));
    }
  }

  const filtered = watchlist.filter((item) =>
    item.ticker.toLowerCase().includes(search.toLowerCase()) ||
    (item.company_name || "").toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-[var(--text-muted)]">Lade Watchlist...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Watchlist</p>
          <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Alle Ticker</h1>
          <p className="text-sm text-[var(--text-secondary)]">{watchlist.length} Symbole unter Beobachtung</p>
        </div>
        <CacheStatus fromCache={fromCache} ageSeconds={dataAge} onRefresh={() => loadWatchlist(true)} refreshing={refreshing || loading} />
        <div className="flex gap-2">
          <button
            onClick={async () => {
              try {
                const result = await api.runWebIntelligenceBatch();
                alert(`Web Intelligence Batch: ${result.processed} verarbeitet`);
              } catch {
                alert("Batch fehlgeschlagen — TAVILY_API_KEY gesetzt?");
              }
            }}
            className="flex items-center gap-2 rounded-lg border
                       border-[var(--border)] px-4 py-2 text-sm
                       font-medium text-[var(--text-secondary)]
                       hover:bg-[var(--bg-tertiary)] transition-all"
            title="Web Intelligence für alle Ticker aktualisieren"
          >
            🌐 Web-Scan
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus size={16} />
            Ticker hinzufügen
          </button>
        </div>
      </div>

      <div className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2">
        <Search size={16} className="text-[var(--text-muted)] shrink-0" />
        <input
          type="text"
          placeholder="Ticker oder Name suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--border)] bg-[var(--bg-tertiary)]">
            <tr>
              <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Ticker</th>
              <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Name</th>
              <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Sektor</th>
              <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Kurs</th>
              <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">1T %</th>
              <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Opp</th>
              <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Torp</th>
              <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Empfehlung</th>
              <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Notizen</th>
              <th className="px-4 py-3 text-center font-semibold text-[var(--text-secondary)] w-28">
                Web-Prio
              </th>
              <th className="px-4 py-3 text-center font-semibold text-[var(--text-secondary)]">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.ticker} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)]">
                <td className="px-4 py-3">
                  <Link
                    href={`/research/${item.ticker}`}
                    className="font-semibold text-[var(--accent-blue)] hover:underline"
                  >
                    {item.ticker}
                  </Link>
                  <Link
                    href={`/watchlist/${item.ticker}`}
                    className="ml-2 text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                    title="News & Track Record"
                  >
                    ↗
                  </Link>
                </td>
                <td className="px-4 py-3 text-[var(--text-primary)]">
                  <Link
                    href={`/research/${item.ticker}`}
                    className="text-[var(--accent-blue)] hover:underline"
                  >
                    {item.company_name || "-"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">{item.sector || "-"}</td>
                <td className="px-4 py-3 text-right text-[var(--text-primary)]">
                  ${item.price?.toFixed(2) || "--"}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    item.change_1d_pct && item.change_1d_pct >= 0
                      ? "text-[var(--accent-green)]"
                      : "text-[var(--accent-red)]"
                  }`}
                >
                  {item.change_1d_pct !== undefined ? `${item.change_1d_pct.toFixed(2)}%` : "--"}
                </td>
                <td className="px-4 py-3 text-right text-[var(--accent-purple)]">
                  {item.opportunity_score ?? "--"}
                </td>
                <td className="px-4 py-3 text-right text-[var(--accent-red)]">
                  {item.torpedo_score ?? "--"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded px-2 py-1 text-xs font-semibold ${
                      item.recommendation === "Strong Buy"
                        ? "bg-green-900/30 text-[var(--accent-green)]"
                        : item.recommendation === "Hold"
                        ? "bg-amber-900/30 text-[var(--accent-amber)]"
                        : item.recommendation === "Short"
                        ? "bg-red-900/30 text-[var(--accent-red)]"
                        : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                    }`}
                  >
                    {item.recommendation || "N/A"}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  <span className="line-clamp-1">{item.notes || "-"}</span>
                </td>
                <td className="px-4 py-3 text-center">
                  <select
                    value={item.web_prio ?? "auto"}
                    onChange={(e) => {
                      const val = e.target.value;
                      const newPrio = val === "auto" ? null : parseInt(val);
                      // Optimistic Update: sofort den State ändern
                      setWatchlist(prev => prev.map(w => 
                        w.ticker === item.ticker 
                          ? { ...w, web_prio: newPrio }
                          : w
                      ));
                      // Dann Backend Update
                      handleUpdateWebPrio(item.ticker, newPrio);
                    }}
                    className="rounded-lg border border-[var(--border)]
                               bg-[var(--bg-tertiary)] px-2 py-1 text-xs
                               text-[var(--text-primary)] outline-none
                               focus:border-[var(--accent-blue)]"
                    title="Web Intelligence Priorität"
                  >
                    <option value="auto">Auto</option>
                    <option value="1">🔴 P1 · 3×/Tag</option>
                    <option value="2">🟡 P2 · 1×/Tag</option>
                    <option value="3">🟢 P3 · Wöchentlich</option>
                    <option value="4">⚫ P4 · Pausiert</option>
                  </select>
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => handleRemoveTicker(item.ticker)}
                    className="text-[var(--accent-red)] hover:opacity-70"
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showAddModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}
        >
          <div className="w-full max-w-md rounded-2xl border border-[var(--border)]
                          bg-[var(--bg-secondary)] p-6 shadow-2xl">

            {/* Header */}
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                Ticker hinzufügen
              </h2>
              <button
                onClick={closeModal}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]
                           transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Felder */}
            <div className="space-y-3">

              {/* Ticker — wichtigstes Feld, hervorgehoben */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Ticker <span className="text-[var(--accent-red)]">*</span>
                </label>
                <input
                  type="text"
                  placeholder="z.B. MU, AAPL, NVDA"
                  value={newTicker.ticker}
                  onChange={(e) => {
                    setNewTicker({ ...newTicker, ticker: e.target.value.toUpperCase() });
                    setAddError(null);
                  }}
                  onKeyDown={(e) => { if (e.key === "Enter") handleAddTicker(); }}
                  autoFocus
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             font-mono font-semibold uppercase tracking-wider
                             text-[var(--text-primary)] outline-none
                             placeholder:text-[var(--text-muted)] placeholder:normal-case
                             placeholder:font-normal placeholder:tracking-normal
                             focus:border-[var(--accent-blue)]"
                />
              </div>

              {/* Firmenname — optional */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Firmenname
                  <span className="ml-1 text-[var(--text-muted)] font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Wird aus Ticker abgeleitet wenn leer"
                  value={newTicker.company_name}
                  onChange={(e) => setNewTicker({ ...newTicker, company_name: e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             text-[var(--text-primary)] outline-none
                             placeholder:text-[var(--text-muted)]
                             focus:border-[var(--accent-blue)]"
                />
              </div>

              {/* Sektor — optional */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Sektor
                  <span className="ml-1 text-[var(--text-muted)] font-normal">(optional)</span>
                </label>
                <select
                  value={newTicker.sector}
                  onChange={(e) => setNewTicker({ ...newTicker, sector: e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             text-[var(--text-primary)] outline-none
                             focus:border-[var(--accent-blue)]"
                >
                  <option value="">Sektor auswählen...</option>
                  <option value="Technology">Technology</option>
                  <option value="Healthcare">Healthcare</option>
                  <option value="Financials">Financials</option>
                  <option value="Consumer Discretionary">Consumer Discretionary</option>
                  <option value="Consumer Staples">Consumer Staples</option>
                  <option value="Industrials">Industrials</option>
                  <option value="Energy">Energy</option>
                  <option value="Materials">Materials</option>
                  <option value="Real Estate">Real Estate</option>
                  <option value="Utilities">Utilities</option>
                  <option value="Communication Services">Communication Services</option>
                  <option value="Crypto">Crypto</option>
                  <option value="Unknown">Unbekannt</option>
                </select>
              </div>

              {/* Notizen */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Notizen
                  <span className="ml-1 text-[var(--text-muted)] font-normal">(optional)</span>
                </label>
                <textarea
                  placeholder="Trading-These, Catalyst, Erinnerung..."
                  value={newTicker.notes}
                  onChange={(e) => setNewTicker({ ...newTicker, notes: e.target.value })}
                  rows={2}
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             text-[var(--text-primary)] outline-none resize-none
                             placeholder:text-[var(--text-muted)]
                             focus:border-[var(--accent-blue)]"
                />
              </div>
            </div>

            {/* Error-Anzeige */}
            {addError && (
              <div className="mt-3 rounded-lg border border-[var(--accent-red)]/30
                              bg-[var(--accent-red)]/10 px-4 py-3 text-sm
                              text-[var(--accent-red)]">
                ⚠ {addError}
              </div>
            )}

            {/* Buttons */}
            <div className="mt-5 flex gap-3">
              <button
                onClick={handleAddTicker}
                disabled={addLoading || !newTicker.ticker.trim()}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg
                           bg-[var(--accent-blue)] px-4 py-2.5 text-sm font-semibold
                           text-white transition-all hover:opacity-90
                           disabled:cursor-not-allowed disabled:opacity-40"
              >
                {addLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2
                                    border-white/30 border-t-white" />
                    Wird hinzugefügt...
                  </>
                ) : (
                  <>+ Zur Watchlist</>
                )}
              </button>
              <button
                onClick={closeModal}
                disabled={addLoading}
                className="rounded-lg border border-[var(--border)] px-4 py-2.5
                           text-sm font-medium text-[var(--text-secondary)]
                           transition-all hover:bg-[var(--bg-tertiary)]
                           disabled:opacity-40"
              >
                Abbrechen
              </button>
            </div>

            {/* Hinweis */}
            <p className="mt-3 text-center text-xs text-[var(--text-muted)]">
              Nur Ticker ist Pflichtfeld · Escape zum Schließen
            </p>

          </div>
        </div>
      )}
    </div>
  );
}
