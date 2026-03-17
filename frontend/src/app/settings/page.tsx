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
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-4xl font-bold text-[var(--text-primary)]">Settings</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">System Diagnostics & Configuration</p>
      </div>

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">System Check</h2>
          <button
            onClick={runDiagnostics}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <Play size={18} />
            {loading ? "Running..." : "Run Diagnostics"}
          </button>
        </div>

        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
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
              <div key={key} className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">{label}</h3>
                  {getStatusIcon(status?.status)}
                </div>
                <p className="text-xs text-[var(--text-muted)] leading-relaxed">{status?.details || "Not tested yet"}</p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Database Status</h2>
          <button
            onClick={loadDbStatus}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-6 py-3 text-sm font-medium text-[var(--text-primary)] shadow-sm hover:bg-[var(--bg-tertiary)] disabled:opacity-50 transition-all"
          >
            <Database size={18} />
            {loading ? "Loading..." : "Load DB Status"}
          </button>
        </div>

        <div className="card p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Table</th>
                  <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Row Count</th>
                </tr>
              </thead>
              <tbody>
                {dbStatus.tables && dbStatus.tables.length > 0 ? (
                  dbStatus.tables.map((table, idx) => (
                    <tr key={idx} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors">
                      <td className="px-4 py-4 font-medium text-[var(--text-primary)]">{table.table_name}</td>
                      <td className="px-4 py-4 text-right text-[var(--text-primary)]">{table.row_count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2} className="px-4 py-12 text-center text-[var(--text-muted)]">
                      No data available. Click "Load DB Status".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">Telegram Test</h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4 leading-relaxed">
            Sends a test message to your Telegram bot.
          </p>
          <button
            onClick={testTelegram}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <Play size={18} />
            Send Test Message
          </button>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">n8n Workflows</h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4 leading-relaxed">
            Automatically sets up all n8n workflows.
          </p>
          <button
            onClick={setupN8n}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-purple)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <Play size={18} />
            Setup Workflows
          </button>
        </div>
      </div>
    </div>
  );
}
