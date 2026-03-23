"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Brain, TrendingUp, Info, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";

type SnapshotStats = {
  total: number;
  with_outcome: number;
  correct_t5: number;
  accuracy_t5_pct: number | null;
  avg_return_t5: number | null;
  data_quality_issues: number;
  by_recommendation: Record<string, { total: number; correct: number }>;
};

type LernpfadeData = {
  earnings: SnapshotStats;
  momentum: SnapshotStats;
  total_snapshots: number;
  min_snapshots_for_calibration: number;
  calibration_ready: boolean;
};

function StatCard({
  label, value, sub, color = ""
}: {
  label: string; value: string; sub?: string; color?: string
}) {
  return (
    <div className="card p-3">
      <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className={`text-2xl font-bold font-mono ${color || "text-[var(--text-primary)]"}`}>
        {value}
      </p>
      {sub && (
        <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{sub}</p>
      )}
    </div>
  );
}

function PathCard({
  type, stats, minRequired
}: {
  type: "earnings" | "momentum";
  stats: SnapshotStats;
  minRequired: number;
}) {
  const [open, setOpen] = useState(true);
  const isEarnings = type === "earnings";
  const color  = isEarnings ? "var(--accent-blue)" : "var(--accent-green)";
  const label  = isEarnings ? "Lernpfad A — Earnings Intelligence" : "Lernpfad B — Momentum & Narrative";
  const icon   = isEarnings ? "📊" : "📈";
  const pct    = stats.accuracy_t5_pct;
  const pctStr = pct !== null ? `${pct.toFixed(0)}%` : "—";
  const pctColor = pct === null ? "" :
    pct >= 65 ? "text-[var(--accent-green)]" :
    pct >= 50 ? "text-amber-400" : "text-[var(--accent-red)]";
  const progress = Math.min((stats.total / minRequired) * 100, 100);
  const ready = stats.with_outcome >= minRequired;

  return (
    <div className="card" style={{ borderLeft: `4px solid ${color}` }}>
      <div
        className="flex items-center justify-between p-4 cursor-pointer"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2">
          <span className="text-base">{icon}</span>
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {label}
          </p>
          {ready ? (
            <span className="text-[10px] px-2 py-0.5 rounded font-medium
                             bg-[var(--accent-green)]/10 text-[var(--accent-green)]">
              Kalibrierbar
            </span>
          ) : (
            <span className="text-[10px] px-2 py-0.5 rounded font-medium
                             bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
              Daten sammeln
            </span>
          )}
        </div>
        {open
          ? <ChevronUp size={14} className="text-[var(--text-muted)]" />
          : <ChevronDown size={14} className="text-[var(--text-muted)]" />}
      </div>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-[var(--border)] pt-3">

          {/* Progress zur Kalibrierung */}
          {!ready && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] text-[var(--text-muted)]">
                  Datenbasis für Kalibrierung
                </p>
                <p className="text-[10px] font-mono text-[var(--text-muted)]">
                  {stats.with_outcome} / {minRequired} Outcomes
                </p>
              </div>
              <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)]">
                <div
                  className="h-1.5 rounded-full transition-all"
                  style={{
                    width: `${progress}%`,
                    background: color,
                  }}
                />
              </div>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">
                Ab {minRequired} ausgewerteten Trades: Score-Gewichtungen
                können für diesen Pfad separat kalibriert werden.
              </p>
            </div>
          )}

          {/* Metriken */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Snapshots gesamt"
              value={stats.total.toString()}
              sub={`${stats.with_outcome} ausgewertet`}
            />
            <StatCard
              label="T+5 Trefferquote"
              value={pctStr}
              sub="Richtung korrekt"
              color={pctColor}
            />
            <StatCard
              label="Ø Return T+5"
              value={stats.avg_return_t5 !== null
                ? `${stats.avg_return_t5 >= 0 ? "+" : ""}${stats.avg_return_t5.toFixed(1)}%` 
                : "—"}
              sub="nach 5 Handelstagen"
              color={(stats.avg_return_t5 || 0) >= 0
                ? "text-[var(--accent-green)]"
                : "text-[var(--accent-red)]"}
            />
            <StatCard
              label="Daten-Lücken"
              value={stats.data_quality_issues.toString()}
              sub="stale_data Flags"
              color={stats.data_quality_issues > 2 ? "text-amber-400" : ""}
            />
          </div>

          {/* Erklärungs-Block */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-3 space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider
                         text-[var(--text-muted)]">
              Was dieser Lernpfad misst
            </p>
            {isEarnings ? (
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Kafins Fähigkeit die <strong className="text-[var(--text-primary)]">Erwartungslücke</strong> vor
                Earnings richtig einzuschätzen. Dominante Signale: Whisper-Delta,
                Earnings-Momentum (Beat-Serie), Guidance-Trend, Insider-Aktivität.
                RSI und technisches Setup spielen hier eine untergeordnete Rolle —
                weil Earnings den Kurs unabhängig von der technischen Lage bewegen.
                <br /><br />
                <strong className="text-[var(--text-primary)]">Haupt-Outcome-Metrik:</strong> T+1
                Overnight-Reaktion. T+5 als Bestätigung.
                T+20 als Thesis-Validierung (war der Earnings-Impuls nachhaltig?).
              </p>
            ) : (
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Kafins Fähigkeit <strong className="text-[var(--text-primary)]">Momentum und Narrative Shifts</strong> früh
                zu erkennen. Dominante Signale: Relative Stärke vs. SPY,
                Narrative Shift (is_narrative_shift), RVOL-Spike, SMA50-Cross,
                Sektor-Kapitalfluss. Earnings-Surprise aus vergangenen Quartalen
                spielt hier kaum eine Rolle — der Markt hat es verdaut.
                <br /><br />
                <strong className="text-[var(--text-primary)]">Haupt-Outcome-Metrik:</strong> Stop-Hit
                vs. Target-Hit. T+20 als Thesis-Check.
              </p>
            )}
          </div>

          {/* Nach Kalibrierung verfügbar */}
          {ready && (
            <div className="rounded-lg border border-[var(--accent-green)]/30
                            bg-[var(--accent-green)]/5 p-3">
              <p className="text-xs font-semibold text-[var(--accent-green)] mb-1">
                ✓ Kalibrierung verfügbar
              </p>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Du hast genug Outcome-Daten um die Score-Gewichtungen für
                diesen Pfad zu analysieren. Gehe zu{" "}
                <strong className="text-[var(--text-primary)]">Einstellungen → Konfiguration → Scoring</strong>{" "}
                und vergleiche die Trefferquoten je Faktor. Dann entscheide
                ob Anpassungen sinnvoll sind.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function LernpfadePage() {
  const [data, setData] = useState<LernpfadeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showFuture, setShowFuture] = useState(false);

  useEffect(() => {
    api.getLernpfadeStats()
       .then(setData)
       .catch(console.error)
       .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] p-4 md:p-6 space-y-5">

      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/performance"
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-lg font-bold text-[var(--text-primary)]">
            Lernpfade
          </h1>
          <p className="text-xs text-[var(--text-muted)]">
            Wie Kafin aus Earnings- und Momentum-Trades lernt
          </p>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--text-muted)]">Lade...</p>
      ) : data ? (
        <>
          {/* Gesamt-Fortschritt */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em]
                           text-[var(--text-muted)]">
                Gesamt-Datenbasis
              </p>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                data.calibration_ready
                  ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
              }`}>
                {data.calibration_ready
                  ? "Score-Kalibrierung möglich"
                  : `${data.total_snapshots} / ${data.min_snapshots_for_calibration * 2} Snapshots`}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Kafin speichert bei jedem Audit-Report einen{" "}
              <strong className="text-[var(--text-primary)]">Decision Snapshot</strong> —
              den vollständigen Entscheidungs-Kontext: Scores, Makro, Rohdaten,
              KI-Prompt, Top-Treiber. Danach werden die Outcomes automatisch
              nachgepflegt (T+1, T+5, T+20, Stop-Hit, Target-Hit).
              <br /><br />
              Ab <strong className="text-[var(--text-primary)]">{data.min_snapshots_for_calibration} Outcomes pro Pfad</strong>{" "}
              kannst du erkennen ob die Score-Gewichtungen für deinen Trading-Stil
              passen — und wo Kafin systematisch daneben liegt.
            </p>
          </div>

          {/* Zwei Pfade */}
          <PathCard
            type="earnings"
            stats={data.earnings}
            minRequired={data.min_snapshots_for_calibration}
          />
          <PathCard
            type="momentum"
            stats={data.momentum}
            minRequired={data.min_snapshots_for_calibration}
          />

          {/* Zukunftsvision */}
          <div className="card">
            <div
              className="flex items-center justify-between p-4 cursor-pointer"
              onClick={() => setShowFuture(f => !f)}
            >
              <div className="flex items-center gap-2">
                <Brain size={14} className="text-[var(--accent-blue)]" />
                <p className="text-xs font-semibold text-[var(--text-primary)]">
                  Zukünftige Entwicklung — Separate Scoring-Engines
                </p>
              </div>
              {showFuture
                ? <ChevronUp size={14} className="text-[var(--text-muted)]" />
                : <ChevronDown size={14} className="text-[var(--text-muted)]" />}
            </div>
            {showFuture && (
              <div className="px-4 pb-4 border-t border-[var(--border)] pt-3 space-y-3">
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  Heute nutzt Kafin <strong className="text-[var(--text-primary)]">einen universellen Opp-Score</strong> mit
                  festen Gewichtungen — egal ob es ein Earnings-Trade oder
                  ein Momentum-Trade ist. Das ist der pragmatische Start.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {[
                    {
                      phase: "Phase 1 — Heute",
                      desc: "Ein universeller Score, beide Trade-Typen. Outcomes werden getrennt gespeichert (trade_type). Trefferquoten pro Pfad werden sichtbar.",
                      status: "✅ Aktiv",
                      color: "text-[var(--accent-green)]",
                    },
                    {
                      phase: "Phase 2 — ab 15+ Outcomes/Pfad",
                      desc: "Analyse: Bei welchem Pfad weichen die Faktor-Treiber von der tatsächlichen Kursreaktion ab? Manuelle Score-Gewichtungs-Anpassung in scoring.yaml.",
                      status: "⏳ Warte auf Daten",
                      color: "text-amber-400",
                    },
                    {
                      phase: "Phase 3 — Separate Scoring-Engines",
                      desc: "scoring_earnings.yaml + scoring_momentum.yaml. generate_audit_report() wählt Profil basierend auf earnings_countdown. Zwei unabhängige Kalibrierungs-Kurven.",
                      status: "🔮 Zukunft",
                      color: "text-[var(--text-muted)]",
                    },
                    {
                      phase: "Phase 4 — Adaptive Gewichtung",
                      desc: "Score-Gewichtungen passen sich automatisch an historische Trefferquoten an. Erst sinnvoll ab 50+ Outcomes pro Pfad und pro Makro-Regime.",
                      status: "🔮 Langfristig",
                      color: "text-[var(--text-muted)]",
                    },
                  ].map(p => (
                    <div key={p.phase}
                      className="rounded-lg bg-[var(--bg-tertiary)] p-3">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs font-semibold text-[var(--text-primary)]">
                          {p.phase}
                        </p>
                        <span className={`text-[10px] font-medium ${p.color}`}>
                          {p.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                        {p.desc}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="card p-12 text-center">
          <p className="text-sm text-[var(--text-muted)]">
            Keine Daten verfügbar.
          </p>
        </div>
      )}
    </div>
  );
}
