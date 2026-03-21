"use client";

import { Info, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function MarketsInfoPage() {
  const refreshLegend = [
    { label: "60s", value: "Indizes / Sektoren / Makro-Proxys", description: "Globale Aktienindizes, Sektoren-Heatmap und makroökonomische Proxy-Indikatoren" },
    { label: "5m", value: "Marktbreite", description: "Anteil der Aktien über重要的 gleitenden Durchschnitten (SMA50/200)" },
    { label: "10m", value: "Cross-Asset / News", description: "VIX-Struktur, Risk Appetite, Credit-Spreads und Nachrichten mit Sentiment-Analyse" },
    { label: "30m", value: "Makro / Kalender", description: "Wirtschaftskalender, makroökonomische Indikatoren und Zinsstruktur" },
  ];

  const blocks = [
    { id: "1", name: "Globale Indizes", cadence: "60s", description: "SPY, QQQ, DIA, IWM, DAX, Euro Stoxx 50, Nikkei 225, MSCI World" },
    { id: "2", name: "Sektor-Rotation", cadence: "60s", description: "11 US-Sektor-ETFs mit farbcodierter Performance und Trend-Richtung" },
    { id: "3", name: "Marktbreite", cadence: "5m", description: "% Aktien über SMA50/200 aus S&P 500 Top 50 Sample" },
    { id: "4", name: "Wirtschaftskalender", cadence: "30m", description: "48h Events mit Impact-Bewertung und Filter nach Ländern" },
    { id: "5", name: "Cross-Asset Signale", cadence: "10m", description: "VIX-Struktur, Risk Appetite, Credit-Spreads, Yield Curve" },
    { id: "6", name: "News + FinBERT", cadence: "10m", description: "Markt-Headlines mit KI-Sentiment-Analyse und Kategorisierung" },
    { id: "7", name: "Makro-Dashboard", cadence: "30m", description: "Fed Funds Rate, VIX, Credit Spreads, Yield Curve" },
    { id: "8", name: "KI-Markt-Audit", cadence: "Manual", description: "DeepSeek Analyse auf Knopfdruck mit komplexer Marktinterpretation" },
    { id: "9", name: "Makro-Proxys", cadence: "60s", description: "Alternative makroökonomische Indikatoren und Proxy-Messungen" },
  ];

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Link 
            href="/markets"
            className="flex items-center gap-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <ArrowLeft size={16} />
            Zurück zum Dashboard
          </Link>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Info size={24} className="text-[var(--accent-blue)]" />
            <h1 className="text-3xl font-bold text-[var(--text-primary)]">Markets Dashboard v2 - Info</h1>
          </div>
          <p className="text-[var(--text-secondary)]">
            Detaillierte Beschreibung des Markets Dashboard v2 mit allen Datenblöcken, Refresh-Zyklen und Funktionsweisen.
          </p>
        </div>

        {/* Overview */}
        <div className="card p-6 border border-[var(--border)] bg-[var(--bg-secondary)]">
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-4">Überblick</h2>
          <div className="space-y-3 text-sm text-[var(--text-secondary)]">
            <p>
              Das Markets Dashboard v2 bietet eine <span className="font-semibold text-[var(--text-primary)]">granulare Echtzeit-Marktanalyse</span> mit individuellen Refresh-Zyklen.
              Die Seite zeigt Marktregime, Breite, Sektoren, Cross-Asset-Signale, News-Sentiment, den Wirtschaftskalender und den KI-Markt-Audit in einem gemeinsamen Layout.
            </p>
            <p>
              Jeder Datenblock hat seinen eigenen Refresh-Rhythmus, um Datenfrische zu gewährleisten und unnötige API-Aufrufe zu vermeiden.
              Timestamps zeigen die letzte Aktualisierung an, mit Warnungen bei veralteten Daten.
            </p>
          </div>
        </div>

        {/* Refresh Legend */}
        <div className="card p-6 border border-[var(--border)] bg-[var(--bg-secondary)]">
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-4">Refresh-Zyklen</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {refreshLegend.map((item) => (
              <div key={item.label} className="rounded-lg bg-[var(--bg-tertiary)] p-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="text-sm font-bold uppercase tracking-widest text-[var(--accent-blue)]">
                    {item.label}
                  </div>
                </div>
                <div className="font-semibold text-[var(--text-primary)] mb-1">{item.value}</div>
                <div className="text-xs text-[var(--text-secondary)]">{item.description}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Data Blocks */}
        <div className="card p-6 border border-[var(--border)] bg-[var(--bg-secondary)]">
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-4">Datenblöcke (9 Blöcke)</h2>
          <div className="space-y-4">
            {blocks.map((block) => (
              <div key={block.id} className="border-l-4 border-[var(--accent-blue)] pl-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="rounded-full bg-[var(--bg-tertiary)] px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                    Block {block.id}
                  </span>
                  <span className="text-[11px] uppercase tracking-[0.18em] text-[var(--accent-blue)]">
                    {block.cadence} Refresh
                  </span>
                  <h3 className="font-semibold text-[var(--text-primary)]">{block.name}</h3>
                </div>
                <p className="text-sm text-[var(--text-secondary)]">{block.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Technical Details */}
        <div className="card p-6 border border-[var(--border)] bg-[var(--bg-secondary)]">
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-4">Technische Details</h2>
          <div className="space-y-3 text-sm text-[var(--text-secondary)]">
            <div>
              <span className="font-semibold text-[var(--text-primary)]">News + FinBERT:</span>
              Analysiert relevante Markt-Headlines mit KI-Sentiment-Analyse. Wenn keine Headlines verfügbar sind, bleibt die Karte sichtbar und zeigt den Status.
            </div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Error Handling:</span>
              Robuste Fehlerbehandlung mit Fallback-Komponenten bei API-Ausfällen.
            </div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Datenquellen:</span>
              Finnhub (News, Indizes), FMP (Makro-Daten), interne Berechnungen (Marktbreite, Sektoren).
            </div>
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Performance:</span>
              Promise.allSettled für parallele API-Aufrufe, individuelle State-Verwaltung pro Block.
            </div>
          </div>
        </div>

        {/* Navigation Tip */}
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-tertiary)] p-4 text-sm text-[var(--text-muted)]">
          <div className="flex items-center gap-2">
            <Info size={16} />
            <span>
              Klicke auf das "i" Icon im Dashboard Header, um jederzeit zu dieser Info-Seite zurückzukehren.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
