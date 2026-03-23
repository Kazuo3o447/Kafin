"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Plus, Trash2, Check, X, ChevronDown, ChevronUp, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";

type JournalEntry = {
  id: number;
  ticker: string;
  direction: "long" | "short";
  entry_date: string;
  entry_price: number;
  shares: number | null;
  stop_price: number | null;
  target_price: number | null;
  thesis: string | null;
  opportunity_score: number | null;
  torpedo_score: number | null;
  recommendation: string | null;
  exit_date: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  notes: string | null;
  pnl: number | null;
  pnl_pct: number | null;
};

const EXIT_REASONS = [
  { value: "stop_hit",          label: "Stop gerissen" },
  { value: "target_hit",        label: "Ziel erreicht" },
  { value: "manual",            label: "Manuell geschlossen" },
  { value: "earnings_reaction", label: "Earnings-Reaktion" },
];

function fmt(n: number | null, digits = 2, prefix = "") {
  if (n == null) return "—";
  return `${prefix}${n.toFixed(digits)}`;
}

export default function JournalPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [exitId, setExitId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Neuer Eintrag — Formular-State
  const [form, setForm] = useState({
    ticker: "", direction: "long", entry_date: new Date().toISOString().slice(0, 10),
    entry_price: "", shares: "", stop_price: "", target_price: "", thesis: "",
    opportunity_score: "", torpedo_score: "", recommendation: "", notes: "",
  });

  // Exit — Formular-State
  const [exitForm, setExitForm] = useState({
    exit_date: new Date().toISOString().slice(0, 10),
    exit_price: "", exit_reason: "manual", notes: "",
  });

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getJournal();
      setEntries(res.entries || []);
    } catch (e: any) {
      console.error("Journal laden fehlgeschlagen:", e?.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  async function handleCreate() {
    if (!form.ticker || !form.entry_price || !form.entry_date) return;
    try {
      await api.createJournalEntry({
        ticker: form.ticker.toUpperCase(),
        direction: form.direction,
        entry_date: form.entry_date,
        entry_price: parseFloat(form.entry_price),
        shares: form.shares ? parseFloat(form.shares) : null,
        stop_price: form.stop_price ? parseFloat(form.stop_price) : null,
        target_price: form.target_price ? parseFloat(form.target_price) : null,
        thesis: form.thesis || null,
        opportunity_score: form.opportunity_score ? parseFloat(form.opportunity_score) : null,
        torpedo_score: form.torpedo_score ? parseFloat(form.torpedo_score) : null,
        recommendation: form.recommendation || null,
        notes: form.notes || null,
      });
      setShowForm(false);
      setForm({
        ticker: "", direction: "long", entry_date: new Date().toISOString().slice(0, 10),
        entry_price: "", shares: "", stop_price: "", target_price: "", thesis: "",
        opportunity_score: "", torpedo_score: "", recommendation: "", notes: "",
      });
      loadEntries();
    } catch (e: any) {
      console.error("Eintrag erstellen fehler:", e?.message);
    }
  }

  async function handleExit(id: number) {
    if (!exitForm.exit_price || !exitForm.exit_date) return;
    try {
      await api.updateJournalEntry(id, {
        exit_date: exitForm.exit_date,
        exit_price: parseFloat(exitForm.exit_price),
        exit_reason: exitForm.exit_reason,
        notes: exitForm.notes || undefined,
      });
      setExitId(null);
      loadEntries();
    } catch (e: any) {
      console.error("Exit eintragen fehler:", e?.message);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Eintrag löschen?")) return;
    try {
      await api.deleteJournalEntry(id);
      loadEntries();
    } catch (e: any) {
      console.error("Löschen fehler:", e?.message);
    }
  }

  const open = entries.filter(e => !e.exit_date);
  const closed = entries.filter(e => e.exit_date);
  const totalPnl = closed.reduce((s, e) => s + (e.pnl ?? 0), 0);
  const winners = closed.filter(e => (e.pnl ?? 0) > 0).length;
  const winRate = closed.length > 0 ? Math.round((winners / closed.length) * 100) : null;

  const inputCls = "w-full rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none";

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] p-4 md:p-6 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <ArrowLeft size={18} />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">Trade Journal</h1>
            <p className="text-xs text-[var(--text-muted)]">Echte Positionen · Strukturiertes Lernen</p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
        >
          <Plus size={14} />
          Neuer Trade
        </button>
      </div>

      {/* Statistiken */}
      {closed.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Gesamt P&L", value: `${totalPnl >= 0 ? "+" : ""}$${Math.abs(totalPnl).toFixed(0)}`, color: totalPnl >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]" },
            { label: "Trefferquote", value: winRate != null ? `${winRate}%` : "—", color: "text-[var(--text-primary)]" },
            { label: "Abgeschlossen", value: closed.length.toString(), color: "text-[var(--text-primary)]" },
            { label: "Offen", value: open.length.toString(), color: "text-[var(--accent-blue)]" },
          ].map(s => (
            <div key={s.label} className="card p-3">
              <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">{s.label}</p>
              <p className={`text-xl font-bold font-mono ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Neuer Eintrag — Formular */}
      {showForm && (
        <div className="card p-4 space-y-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">
            Neuer Trade
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { key: "ticker", label: "Ticker", placeholder: "AAPL" },
              { key: "entry_date", label: "Entry-Datum", placeholder: "", type: "date" },
              { key: "entry_price", label: "Entry-Preis ($)", placeholder: "150.00", type: "number" },
              { key: "shares", label: "Anzahl Shares", placeholder: "100", type: "number" },
              { key: "stop_price", label: "Stop-Loss ($)", placeholder: "142.00", type: "number" },
              { key: "target_price", label: "Ziel ($)", placeholder: "165.00", type: "number" },
              { key: "opportunity_score", label: "Opp-Score", placeholder: "7.5", type: "number" },
              { key: "torpedo_score", label: "Torpedo-Score", placeholder: "2.5", type: "number" },
            ].map(f => (
              <div key={f.key}>
                <label className="text-xs text-[var(--text-muted)]">{f.label}</label>
                <input
                  type={f.type || "text"}
                  placeholder={f.placeholder}
                  value={(form as any)[f.key]}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  className={inputCls}
                  step={f.type === "number" ? "0.01" : undefined}
                />
              </div>
            ))}
            <div>
              <label className="text-xs text-[var(--text-muted)]">Richtung</label>
              <select value={form.direction} onChange={e => setForm(prev => ({ ...prev, direction: e.target.value }))} className={inputCls}>
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)]">Empfehlung</label>
              <input type="text" placeholder="Strong Buy…" value={form.recommendation}
                onChange={e => setForm(prev => ({ ...prev, recommendation: e.target.value }))} className={inputCls} />
            </div>
          </div>
          <div>
            <label className="text-xs text-[var(--text-muted)]">These</label>
            <textarea value={form.thesis} onChange={e => setForm(prev => ({ ...prev, thesis: e.target.value }))}
              placeholder="Warum dieser Trade? Welches Signal war entscheidend?"
              rows={2} className={`${inputCls} resize-none`} />
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate}
              className="rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm text-white hover:opacity-90">
              Speichern
            </button>
            <button onClick={() => setShowForm(false)}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]">
              Abbrechen
            </button>
          </div>
        </div>
      )}

      {/* Offene Trades */}
      {open.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">
            Offene Positionen ({open.length})
          </p>
          {open.map(e => (
            <div key={e.id} className="card p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3">
                  <Link href={`/research/${e.ticker}`}
                    className="font-mono font-bold text-[var(--accent-blue)] hover:opacity-80">
                    {e.ticker}
                  </Link>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    e.direction === "long"
                      ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                      : "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
                  }`}>{e.direction.toUpperCase()}</span>
                  <span className="text-sm font-mono text-[var(--text-primary)]">
                    ${e.entry_price.toFixed(2)}
                  </span>
                  {e.shares && <span className="text-xs text-[var(--text-muted)]">{e.shares} Shares</span>}
                </div>
                <div className="flex items-center gap-2">
                  {e.opportunity_score && (
                    <span className="text-[10px] text-[var(--accent-green)]">Opp {e.opportunity_score}</span>
                  )}
                  {e.torpedo_score && (
                    <span className="text-[10px] text-[var(--accent-red)]">Torp {e.torpedo_score}</span>
                  )}
                  <button onClick={() => {
                    setExitId(exitId === e.id ? null : e.id);
                    setExitForm({ exit_date: new Date().toISOString().slice(0, 10), exit_price: "", exit_reason: "manual", notes: "" });
                  }}
                    className="rounded-lg bg-[var(--accent-green)]/10 border border-[var(--accent-green)]/30
                               px-3 py-1.5 text-xs text-[var(--accent-green)] hover:bg-[var(--accent-green)]/20">
                    <Check size={12} className="inline mr-1" />Exit
                  </button>
                  <button onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                    className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                    {expandedId === e.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  <button onClick={() => handleDelete(e.id)}
                    className="text-[var(--text-muted)] hover:text-[var(--accent-red)]">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Exit-Formular */}
              {exitId === e.id && (
                <div className="mt-3 pt-3 border-t border-[var(--border)] grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="text-xs text-[var(--text-muted)]">Exit-Datum</label>
                    <input type="date" value={exitForm.exit_date}
                      onChange={ev => setExitForm(p => ({ ...p, exit_date: ev.target.value }))} className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-muted)]">Exit-Preis ($)</label>
                    <input type="number" step="0.01" value={exitForm.exit_price}
                      onChange={ev => setExitForm(p => ({ ...p, exit_price: ev.target.value }))} className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-muted)]">Grund</label>
                    <select value={exitForm.exit_reason}
                      onChange={ev => setExitForm(p => ({ ...p, exit_reason: ev.target.value }))} className={inputCls}>
                      {EXIT_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <button onClick={() => handleExit(e.id)}
                      className="w-full rounded-lg bg-[var(--accent-green)] px-3 py-2 text-sm text-white hover:opacity-90">
                      Bestätigen
                    </button>
                  </div>
                </div>
              )}

              {/* Expandierter Bereich */}
              {expandedId === e.id && (
                <div className="mt-3 pt-3 border-t border-[var(--border)] space-y-2 text-xs text-[var(--text-secondary)]">
                  {e.stop_price && <p>Stop: <span className="text-[var(--accent-red)] font-mono">${e.stop_price.toFixed(2)}</span></p>}
                  {e.target_price && <p>Ziel: <span className="text-[var(--accent-green)] font-mono">${e.target_price.toFixed(2)}</span></p>}
                  {e.thesis && <p className="leading-relaxed">These: {e.thesis}</p>}
                  {e.recommendation && <p>Empfehlung bei Entry: <span className="text-[var(--text-primary)]">{e.recommendation}</span></p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Geschlossene Trades */}
      {closed.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">
            Geschlossene Trades ({closed.length})
          </p>
          {closed.map(e => (
            <div key={e.id} className={`card p-4 border-l-4 ${
              (e.pnl ?? 0) >= 0 ? "border-l-[var(--accent-green)]" : "border-l-[var(--accent-red)]"
            }`}>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-3">
                  <Link href={`/research/${e.ticker}`}
                    className="font-mono font-bold text-[var(--text-primary)] hover:text-[var(--accent-blue)]">
                    {e.ticker}
                  </Link>
                  <span className="text-xs text-[var(--text-muted)]">{e.entry_date} → {e.exit_date}</span>
                  {e.exit_reason && (
                    <span className="text-[10px] text-[var(--text-muted)] border border-[var(--border)] px-2 py-0.5 rounded">
                      {EXIT_REASONS.find(r => r.value === e.exit_reason)?.label ?? e.exit_reason}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  <span className={`font-mono font-bold text-sm ${(e.pnl ?? 0) >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                    {(e.pnl ?? 0) >= 0 ? "+" : ""}${fmt(e.pnl, 0)}
                  </span>
                  <span className={`text-xs font-mono ${(e.pnl_pct ?? 0) >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                    ({(e.pnl_pct ?? 0) >= 0 ? "+" : ""}{fmt(e.pnl_pct, 1)}%)
                  </span>
                  <button onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                    className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                    {expandedId === e.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  <button onClick={() => handleDelete(e.id)}
                    className="text-[var(--text-muted)] hover:text-[var(--accent-red)]">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {expandedId === e.id && (
                <div className="mt-3 pt-3 border-t border-[var(--border)] grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-[var(--text-secondary)]">
                  <p>Entry: <span className="font-mono text-[var(--text-primary)]">${e.entry_price.toFixed(2)}</span></p>
                  <p>Exit: <span className="font-mono text-[var(--text-primary)]">${e.exit_price?.toFixed(2) ?? "—"}</span></p>
                  {e.shares && <p>Shares: <span className="font-mono text-[var(--text-primary)]">{e.shares}</span></p>}
                  {e.opportunity_score && <p>Opp: <span className="text-[var(--accent-green)]">{e.opportunity_score}</span></p>}
                  {e.torpedo_score && <p>Torp: <span className="text-[var(--accent-red)]">{e.torpedo_score}</span></p>}
                  {e.thesis && <p className="col-span-full leading-relaxed">These: {e.thesis}</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && entries.length === 0 && (
        <div className="card p-12 text-center">
          <p className="text-[var(--text-muted)] text-sm">
            Noch keine Trade-Einträge. Klicke „Neuer Trade" um zu starten.
          </p>
        </div>
      )}
    </div>
  );
}
