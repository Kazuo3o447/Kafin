"use client";

import { useState, useEffect } from "react";
import { FileText, Calendar, TrendingUp, Play } from "lucide-react";
import { api } from "@/lib/api";

type Tab = "morning" | "sunday" | "earnings";

function ReportRenderer({ text }: { text: string }) {
  if (!text || text === "Noch kein Report generiert.") {
    return (
      <div className="text-center py-12
                       text-[var(--text-muted)] text-sm">
        Noch kein Report generiert.
      </div>
    );
  }

  // Report in Zeilen aufteilen
  const lines = text.split("\n");
  const sections: Array<{
    type: "section" | "bullet" | "text" | "divider" | "warning" | "action";
    content: string;
    sub?: string;
  }> = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // Haupt-Sections (REGIME:, MARKT:, SEKTOREN: etc.)
    if (/^[A-ZÄÖÜ][A-ZÄÖÜ\s\-&()]+:/.test(line)
        && line.length < 60) {
      const colonIdx = line.indexOf(":");
      sections.push({
        type:    "section",
        content: line.slice(0, colonIdx),
        sub:     line.slice(colonIdx + 1).trim(),
      });
    }
    // Warn-Signale (→ WARNSIGNALE:, → CONTRARIAN:)
    else if (line.startsWith("→")) {
      sections.push({
        type:    "warning",
        content: line.replace(/^→\s*/, ""),
      });
    }
    // Bullets (• oder *)
    else if (line.startsWith("•") || line.startsWith("*")
             || line.startsWith("-")) {
      sections.push({
        type:    "bullet",
        content: line.replace(/^[•*-]\s*/, ""),
      });
    }
    // Aktions-Empfehlungen (Long:, Short:, Hedge:, Cash:)
    else if (/^(Long|Short|Hedge|Cash|Risiko-Appetit):/i
             .test(line)) {
      sections.push({ type: "action", content: line });
    }
    // Trennlinien
    else if (/^[═─=─\-]{3,}$/.test(line)) {
      sections.push({ type: "divider", content: "" });
    }
    // Normaler Text
    else {
      sections.push({ type: "text", content: line });
    }
  }

  return (
    <div className="space-y-1.5 text-sm">
      {sections.map((s, i) => {
        switch (s.type) {

          case "section":
            return (
              <div key={i} className="mt-4 first:mt-0">
                <div className="flex items-baseline
                                 gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold
                                     uppercase tracking-widest
                                     text-[var(--text-muted)]
                                     min-w-[100px]">
                    {s.content}
                  </span>
                  {s.sub && (
                    <span className="text-sm font-semibold
                                       text-[var(--text-primary)]">
                      {s.sub}
                    </span>
                  )}
                </div>
              </div>
            );

          case "bullet":
            return (
              <div key={i}
                   className="flex gap-2 ml-2">
                <span className="text-[var(--accent-blue)]
                                   mt-0.5 shrink-0">
                  ▸
                </span>
                <span className="text-[var(--text-secondary)]
                                   leading-relaxed">
                  {s.content}
                </span>
              </div>
            );

          case "warning":
            return (
              <div key={i}
                   className="flex gap-2 mt-3 rounded-lg
                               bg-[var(--accent-red)]/8
                               border border-[var(--accent-red)]/20
                               px-3 py-2">
                <span className="text-[var(--accent-red)]
                                   shrink-0 text-xs mt-0.5">
                  ⚠
                </span>
                <span className="text-xs
                                   text-[var(--text-secondary)]
                                   leading-relaxed">
                  {s.content}
                </span>
              </div>
            );

          case "action": {
            const colonIdx = s.content.indexOf(":");
            const label    = s.content.slice(0, colonIdx);
            const value    = s.content.slice(colonIdx + 1)
                               .trim();
            const isLong   = /long/i.test(label);
            const isShort  = /short|hedge/i.test(label);
            return (
              <div key={i}
                   className="flex items-baseline gap-2
                               rounded-lg px-3 py-1.5
                               bg-[var(--bg-tertiary)]">
                <span className={`text-[10px] font-bold
                                    uppercase tracking-wider
                                    w-20 shrink-0 ${
                  isLong  ? "text-[var(--accent-green)]"
                : isShort ? "text-[var(--accent-red)]"
                : "text-[var(--text-muted)]"
                }`}>
                  {label}
                </span>
                <span className="text-xs
                                   text-[var(--text-primary)]">
                  {value}
                </span>
              </div>
            );
          }

          case "divider":
            return (
              <hr key={i}
                  className="border-[var(--border)]
                             my-3" />
            );

          default:
            return (
              <p key={i}
                 className="text-[var(--text-secondary)]
                              leading-relaxed pl-2">
                {s.content}
              </p>
            );
        }
      })}
    </div>
  );
}

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("morning");
  const [morningReport, setMorningReport] = useState("");
  const [sundayReport, setSundayReport] = useState("");
  const [earningsReviews, setEarningsReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [archiveDays, setArchiveDays] = useState<Array<{date: string; report: string}>>([]);
  const [archiveOpen, setArchiveOpen] = useState(false);

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

  async function loadArchive() {
    if (archiveDays.length > 0) return;
    try {
      const r = await fetch(
        "/api/reports/morning-archive?days=7"
      );
      const d = await r.json();
      setArchiveDays(d.reports || []);
    } catch {}
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
              <ReportRenderer text={morningReport} />
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={() => {
                setArchiveOpen(!archiveOpen);
                if (!archiveOpen) loadArchive();
              }}
              className="flex items-center gap-2 text-xs
                         text-[var(--text-muted)]
                         hover:text-[var(--text-primary)]
                         transition-colors w-full text-left"
            >
              <span>{archiveOpen ? "▾" : "▸"}</span>
              Letzte 7 Briefings
            </button>

            {archiveOpen && (
              <div className="mt-3 space-y-4">
                {archiveDays.map(day => (
                  <div key={day.date}>
                    <p className="text-[10px] font-semibold
                                   uppercase tracking-wider
                                   text-[var(--text-muted)] mb-2">
                      {new Date(day.date).toLocaleDateString(
                        "de-DE",
                        { weekday:"short", day:"numeric",
                          month:"short" }
                      )}
                    </p>
                    <div className="border border-[var(--border)]
                                     rounded-xl p-4">
                      <ReportRenderer text={day.report} />
                    </div>
                  </div>
                ))}
                {archiveDays.length === 0 && (
                  <p className="text-xs text-[var(--text-muted)]">
                    Noch keine archivierten Briefings.
                  </p>
                )}
              </div>
            )}
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
              <ReportRenderer text={sundayReport} />
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
                {watchlist.map((item, idx) => (
                  <option key={`${item.ticker}-${idx}`} value={item.ticker}>
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
