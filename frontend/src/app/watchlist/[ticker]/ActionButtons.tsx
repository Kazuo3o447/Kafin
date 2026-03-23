"use client";

import { FileText, Calendar } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function ActionButtons({ ticker }: { ticker: string }) {
  return (
    <div className="flex flex-wrap gap-3">
      <button
        onClick={() => {
          fetch(`${API_BASE ? API_BASE : ""}/api/reports/generate/${ticker}`, { method: "POST" })
            .then(() => alert("Audit-Report wird generiert..."))
            .catch(() => alert("Fehler beim Generieren"));
        }}
        className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
      >
        <FileText size={16} />
        Audit-Report generieren
      </button>
      <button
        onClick={() => {
          fetch(`${API_BASE ? API_BASE : ""}/api/reports/post-earnings-review/${ticker}`, { method: "POST" })
            .then(() => alert("Post-Earnings-Review wird gestartet..."))
            .catch(() => alert("Fehler beim Starten"));
        }}
        className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
      >
        <Calendar size={16} />
        Post-Earnings-Review starten
      </button>
    </div>
  );
}
