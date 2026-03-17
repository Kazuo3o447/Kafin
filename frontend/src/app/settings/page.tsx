"use client";

import { useState } from "react";
import { Play, CheckCircle, XCircle, AlertTriangle, Database } from "lucide-react";
import { api } from "@/lib/api";

type DiagnosticResult = {
  supabase?: { status: string; details?: string };
  deepseek?: { status: string; details?: string };
  finnhub?: { status: string; details?: string };
  fmp?: { status: string; details?: string };
  fred?: { status: string; details?: string };
  finbert?: { status: string; details?: string };
  telegram?: { status: string; details?: string };
  n8n?: { status: string; details?: string };
};

type DbStatus = {
  tables?: Array<{ table_name: string; row_count: number }>;
};

export default function SettingsPage() {
  const [diagnostics, setDiagnostics] = useState<DiagnosticResult>({});
  const [dbStatus, setDbStatus] = useState<DbStatus>({});
  const [loading, setLoading] = useState(false);

  async function runDiagnostics() {
    setLoading(true);
    try {
      const result = await api.getDiagnostics();
      setDiagnostics(result);
    } catch (error) {
      console.error("Diagnostics error", error);
    } finally {
      setLoading(false);
    }
  }

  async function loadDbStatus() {
    setLoading(true);
    try {
      const result = await api.getDbStatus();
      setDbStatus(result);
    } catch (error) {
      console.error("DB status error", error);
    } finally {
      setLoading(false);
    }
  }

  async function testTelegram() {
    setLoading(true);
    try {
      await api.testTelegram();
      alert("Telegram-Test-Nachricht wurde gesendet.");
    } catch (error) {
      alert("Fehler beim Telegram-Test.");
    } finally {
      setLoading(false);
    }
  }

  async function setupN8n() {
    setLoading(true);
    try {
      await api.setupN8n();
      alert("n8n-Workflows wurden eingerichtet.");
    } catch (error) {
      alert("Fehler beim Einrichten der n8n-Workflows.");
    } finally {
      setLoading(false);
    }
  }

  function getStatusIcon(status?: string) {
    if (status === "ok" || status === "success") return <CheckCircle size={20} className="text-[var(--accent-green)]" />;
    if (status === "warning") return <AlertTriangle size={20} className="text-[var(--accent-amber)]" />;
    return <XCircle size={20} className="text-[var(--accent-red)]" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Einstellungen</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">System & Diagnostics</h1>
        <p className="text-sm text-[var(--text-secondary)]">Systemcheck, Logs und Konfiguration</p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">Systemcheck</h2>
          <button
            onClick={runDiagnostics}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            <Play size={16} />
            {loading ? "Läuft..." : "Systemcheck starten"}
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            { key: "supabase", label: "Supabase" },
            { key: "deepseek", label: "DeepSeek" },
            { key: "finnhub", label: "Finnhub" },
            { key: "fmp", label: "FMP" },
            { key: "fred", label: "FRED" },
            { key: "finbert", label: "FinBERT" },
            { key: "telegram", label: "Telegram" },
            { key: "n8n", label: "n8n" },
          ].map(({ key, label }) => {
            const status = diagnostics[key as keyof DiagnosticResult];
            return (
              <div key={key} className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">{label}</h3>
                  {getStatusIcon(status?.status)}
                </div>
                <p className="mt-2 text-xs text-[var(--text-muted)]">{status?.details || "Nicht getestet"}</p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">Datenbank-Status</h2>
          <button
            onClick={loadDbStatus}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
          >
            <Database size={16} />
            {loading ? "Lädt..." : "DB-Status laden"}
          </button>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Tabelle</th>
                  <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Anzahl Zeilen</th>
                </tr>
              </thead>
              <tbody>
                {dbStatus.tables && dbStatus.tables.length > 0 ? (
                  dbStatus.tables.map((table, idx) => (
                    <tr key={idx} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)]">
                      <td className="px-4 py-3 text-[var(--text-primary)]">{table.table_name}</td>
                      <td className="px-4 py-3 text-right text-[var(--text-primary)]">{table.row_count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2} className="px-4 py-8 text-center text-[var(--text-muted)]">
                      Keine Daten verfügbar. Klicke auf "DB-Status laden".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-[var(--text-muted)]">Telegram-Test</h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Sendet eine Test-Nachricht an deinen Telegram-Bot.
          </p>
          <button
            onClick={testTelegram}
            disabled={loading}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            <Play size={16} />
            Test-Nachricht senden
          </button>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
          <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-[var(--text-muted)]">n8n-Workflows</h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Richtet alle n8n-Workflows automatisch ein.
          </p>
          <button
            onClick={setupN8n}
            disabled={loading}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-purple)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            <Play size={16} />
            Workflows einrichten
          </button>
        </div>
      </div>
    </div>
  );
}
