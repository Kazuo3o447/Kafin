"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, Trash2, Search } from "lucide-react";
import { api } from "@/lib/api";

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
};

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTicker, setNewTicker] = useState({ ticker: "", company_name: "", sector: "", notes: "" });

  useEffect(() => {
    loadWatchlist();
  }, []);

  async function loadWatchlist() {
    try {
      const data = await api.getWatchlist();
      setWatchlist(data);
    } catch (error) {
      console.error("Watchlist fetch error", error);
    } finally {
      setLoading(false);
    }
  }

  async function handleAddTicker() {
    if (!newTicker.ticker) return;
    try {
      await api.addTicker(newTicker);
      setShowAddModal(false);
      setNewTicker({ ticker: "", company_name: "", sector: "", notes: "" });
      loadWatchlist();
    } catch (error) {
      console.error("Add ticker error", error);
    }
  }

  async function handleRemoveTicker(ticker: string) {
    if (!confirm(`${ticker} wirklich entfernen?`)) return;
    try {
      await api.removeTicker(ticker);
      loadWatchlist();
    } catch (error) {
      console.error("Remove ticker error", error);
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
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus size={16} />
            Ticker hinzufügen
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2">
        <Search size={16} className="text-[var(--text-muted)]" />
        <input
          type="text"
          placeholder="Ticker oder Name suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
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
              <th className="px-4 py-3 text-center font-semibold text-[var(--text-secondary)]">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.ticker} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)]">
                <td className="px-4 py-3">
                  <Link
                    href={`/watchlist/${item.ticker}`}
                    className="font-semibold text-[var(--accent-blue)] hover:underline"
                  >
                    {item.ticker}
                  </Link>
                </td>
                <td className="px-4 py-3 text-[var(--text-primary)]">{item.company_name || "-"}</td>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">Ticker hinzufügen</h2>
            <div className="mt-4 space-y-3">
              <input
                type="text"
                placeholder="Ticker (z.B. AAPL)"
                value={newTicker.ticker}
                onChange={(e) => setNewTicker({ ...newTicker, ticker: e.target.value.toUpperCase() })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
              />
              <input
                type="text"
                placeholder="Firmenname"
                value={newTicker.company_name}
                onChange={(e) => setNewTicker({ ...newTicker, company_name: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
              />
              <input
                type="text"
                placeholder="Sektor"
                value={newTicker.sector}
                onChange={(e) => setNewTicker({ ...newTicker, sector: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
              />
              <textarea
                placeholder="Notizen"
                value={newTicker.notes}
                onChange={(e) => setNewTicker({ ...newTicker, notes: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
                rows={3}
              />
            </div>
            <div className="mt-6 flex gap-2">
              <button
                onClick={handleAddTicker}
                className="flex-1 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
              >
                Hinzufügen
              </button>
              <button
                onClick={() => setShowAddModal(false)}
                className="flex-1 rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
              >
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
