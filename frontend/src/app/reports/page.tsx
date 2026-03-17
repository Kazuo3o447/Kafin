"use client";

import { useState, useEffect } from "react";
import { FileText, Calendar, TrendingUp, Play } from "lucide-react";
import { api } from "@/lib/api";

type Tab = "morning" | "sunday" | "earnings";

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("morning");
  const [morningReport, setMorningReport] = useState("");
  const [sundayReport, setSundayReport] = useState("");
  const [earningsReviews, setEarningsReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);

  useEffect(() => {
    loadLatestReport();
    loadWatchlist();
  }, []);

  async function loadLatestReport() {
    try {
      const data = await api.getLatestReport();
      setMorningReport(data.report || "Noch kein Report generiert.");
    } catch (error) {
      console.error("Latest report fetch error", error);
    }
  }

  async function loadWatchlist() {
    try {
      const data = await api.getWatchlist();
      setWatchlist(data);
    } catch (error) {
      console.error("Watchlist fetch error", error);
    }
  }

  async function generateMorningBriefing() {
    setLoading(true);
    try {
      const result = await api.generateMorningBriefing();
      setMorningReport(result.report || "Report generiert.");
      alert("Morning Briefing wurde generiert und per Telegram versendet.");
    } catch (error) {
      alert("Fehler beim Generieren des Morning Briefings.");
    } finally {
      setLoading(false);
    }
  }

  async function generateSundayReport() {
    setLoading(true);
    try {
      const result = await api.generateSundayReport();
      setSundayReport(result.report || "Report generiert.");
      alert("Sonntags-Report wurde generiert und per Telegram versendet.");
    } catch (error) {
      alert("Fehler beim Generieren des Sonntags-Reports.");
    } finally {
      setLoading(false);
    }
  }

  async function startEarningsReview() {
    if (!selectedTicker) return;
    setLoading(true);
    try {
      await api.postEarningsReview(selectedTicker);
      alert(`Post-Earnings-Review für ${selectedTicker} wurde gestartet.`);
    } catch (error) {
      alert("Fehler beim Starten des Reviews.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Reports</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Generierte Reports</h1>
        <p className="text-sm text-[var(--text-secondary)]">Morning Briefing, Sonntags-Report und Post-Earnings Reviews</p>
      </div>

      <div className="flex gap-2 border-b border-[var(--border)]">
        {[
          { id: "morning" as Tab, label: "Morning Briefing", icon: FileText },
          { id: "sunday" as Tab, label: "Sonntags-Report", icon: Calendar },
          { id: "earnings" as Tab, label: "Post-Earnings Reviews", icon: TrendingUp },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-semibold transition ${
              activeTab === id
                ? "border-[var(--accent-blue)] text-[var(--text-primary)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {activeTab === "morning" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">Morning Briefing</h2>
            <button
              onClick={generateMorningBriefing}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              <Play size={16} />
              {loading ? "Generiere..." : "Jetzt generieren"}
            </button>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
            <p className="mb-2 text-xs uppercase tracking-[0.3em] text-[var(--text-muted)]">Letzter Run</p>
            <pre className="max-h-[600px] overflow-y-auto whitespace-pre-wrap font-mono text-sm text-[var(--text-primary)]">
              {morningReport}
            </pre>
          </div>
        </div>
      )}

      {activeTab === "sunday" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">Sonntags-Report</h2>
            <button
              onClick={generateSundayReport}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              <Play size={16} />
              {loading ? "Generiere..." : "Jetzt generieren"}
            </button>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
            <p className="mb-2 text-xs uppercase tracking-[0.3em] text-[var(--text-muted)]">Letzter Run</p>
            <pre className="max-h-[600px] overflow-y-auto whitespace-pre-wrap font-mono text-sm text-[var(--text-primary)]">
              {sundayReport || "Noch kein Sonntags-Report generiert."}
            </pre>
          </div>
        </div>
      )}

      {activeTab === "earnings" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">Post-Earnings Reviews</h2>
            <div className="flex items-center gap-2">
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none"
              >
                <option value="">Ticker wählen...</option>
                {watchlist.map((item) => (
                  <option key={item.ticker} value={item.ticker}>
                    {item.ticker}
                  </option>
                ))}
              </select>
              <button
                onClick={startEarningsReview}
                disabled={loading || !selectedTicker}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                <Play size={16} />
                {loading ? "Starte..." : "Review starten"}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
            <p className="text-sm text-[var(--text-muted)]">
              Wähle einen Ticker aus der Watchlist und starte einen Post-Earnings-Review. Die Ergebnisse werden in der
              Performance-Seite angezeigt.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
