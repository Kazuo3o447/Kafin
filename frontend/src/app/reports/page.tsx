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
    <div className="space-y-8 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Reports Dashboard</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2">Automatisch generierte Analysen und Reviews</p>
        </div>
      </div>

      {/* Status Overview Cards */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-blue)] bg-opacity-10">
              <FileText size={24} className="text-[var(--accent-blue)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Morning Briefing</p>
              <p className="text-2xl font-bold text-[var(--text-primary)]">Täglich</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">Letzter Run: Heute 08:00</span>
            <span className="badge badge-success">Aktiv</span>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-purple)] bg-opacity-10">
              <Calendar size={24} className="text-[var(--accent-purple)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Sunday Report</p>
              <p className="text-2xl font-bold text-[var(--text-primary)]">Wöchentlich</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">Letzter Run: So 10:00</span>
            <span className="badge badge-neutral">Geplant</span>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-green)] bg-opacity-10">
              <TrendingUp size={24} className="text-[var(--accent-green)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)]">Earnings Reviews</p>
              <p className="text-2xl font-bold text-[var(--text-primary)]">{earningsReviews.length}</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">Gesamt generiert</span>
            <span className="badge badge-info">On-Demand</span>
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        {[
          { id: "morning" as Tab, label: "Morning Briefing", icon: FileText },
          { id: "sunday" as Tab, label: "Sunday Report", icon: Calendar },
          { id: "earnings" as Tab, label: "Earnings Reviews", icon: TrendingUp },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 rounded-lg px-6 py-3 text-sm font-medium transition-all ${
              activeTab === id
                ? "bg-[var(--accent-blue)] text-white shadow-md"
                : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] border border-[var(--border)]"
            }`}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </div>

      {activeTab === "morning" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Morning Briefing</h2>
            <button
              onClick={generateMorningBriefing}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
            >
              <Play size={18} />
              {loading ? "Generiere..." : "Jetzt generieren"}
            </button>
          </div>
          <div className="card p-6">
            <p className="text-sm text-[var(--text-secondary)] mb-4">Letzter Run</p>
            <div className="max-h-[600px] overflow-y-auto rounded-lg bg-[var(--bg-tertiary)] p-6">
              <pre className="whitespace-pre-wrap text-sm text-[var(--text-primary)] leading-relaxed">
                {morningReport}
              </pre>
            </div>
          </div>
        </div>
      )}

      {activeTab === "sunday" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Sunday Report</h2>
            <button
              onClick={generateSundayReport}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
            >
              <Play size={18} />
              {loading ? "Generiere..." : "Jetzt generieren"}
            </button>
          </div>
          <div className="card p-6">
            <p className="text-sm text-[var(--text-secondary)] mb-4">Letzter Run</p>
            <div className="max-h-[600px] overflow-y-auto rounded-lg bg-[var(--bg-tertiary)] p-6">
              <pre className="whitespace-pre-wrap text-sm text-[var(--text-primary)] leading-relaxed">
                {sundayReport || "Noch kein Sunday Report generiert."}
              </pre>
            </div>
          </div>
        </div>
      )}

      {activeTab === "earnings" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Post-Earnings Reviews</h2>
            <div className="flex items-center gap-3">
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none shadow-sm"
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
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
              >
                <Play size={18} />
                {loading ? "Starte..." : "Review starten"}
              </button>
            </div>
          </div>
          <div className="card p-6">
            <p className="text-sm text-[var(--text-primary)] leading-relaxed">
              Wähle einen Ticker aus der Watchlist und starte einen Post-Earnings-Review. Die Ergebnisse werden in der
              Performance-Seite angezeigt.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
