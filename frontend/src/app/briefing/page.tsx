"use client";

import { useState, useEffect, useCallback } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { RefreshCw, Sun, Moon, ArrowLeft, ChevronDown, ChevronUp, Zap } from "lucide-react";
import { api } from "@/lib/api";

type BriefingDay = {
  date: string;
  pre_market: string | null;
  after_market: string | null;
  session_plan: string | null;
  session_plan_at: string | null;
};

function ReportBlock({
  title,
  report,
  icon,
  accentClass,
}: {
  title: string;
  report: string | null;
  icon: ReactNode;
  accentClass: string;
}) {
  const [expanded, setExpanded] = useState(true);

  if (!report) {
    return (
      <div className={`card p-4 border-l-4 ${accentClass} opacity-50`}>
        <div className="flex items-center gap-2">
          {icon}
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            {title}
          </p>
        </div>
        <p className="text-xs text-[var(--text-muted)] mt-2">Noch nicht generiert.</p>
      </div>
    );
  }

  return (
    <div className={`card border-l-4 ${accentClass}`}>
      <div
        className="flex items-center justify-between p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {icon}
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            {title}
          </p>
        </div>
        {expanded ? <ChevronUp size={14} className="text-[var(--text-muted)]" /> : <ChevronDown size={14} className="text-[var(--text-muted)]" />}
      </div>
      {expanded && (
        <div className="px-4 pb-4 border-t border-[var(--border)] pt-3">
          <div className="whitespace-pre-wrap text-sm text-[var(--text-primary)] leading-relaxed">
            {report}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BriefingPage() {
  const [reports, setReports]         = useState<BriefingDay[]>([]);
  const [loading, setLoading]         = useState(true);
  const [generating, setGenerating]   = useState<"pre" | "after" | "plan" | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<{
    pre: boolean;
    after: boolean;
    plan: boolean;
  }>({ pre: true, after: false, plan: true });

  const loadReports = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getBriefingArchive(7);
      const days: BriefingDay[] = res.reports || [];
      setReports(days);
      if (days.length > 0 && !selectedDate) {
        setSelectedDate(days[0].date);
      }
    } catch (e) {
      console.error("Briefing load error", e);
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => { loadReports(); }, []);

  async function triggerPreMarket() {
    setGenerating("pre");
    try {
      await api.generateMorningBriefing();
      await loadReports();
    } catch (e) {
      console.error("Pre-Market generate error", e);
    } finally {
      setGenerating(null);
    }
  }

  async function triggerAfterMarket() {
    setGenerating("after");
    try {
      await api.generateAfterMarketReport();
      await loadReports();
    } catch (e) {
      console.error("After-Market generate error", e);
    } finally {
      setGenerating(null);
    }
  }

  async function triggerSessionPlan() {
    setGenerating("plan");
    try {
      await api.generateSessionPlan();
      await loadReports();
    } catch (e) {
      console.error("Session Plan generate error", e);
    } finally {
      setGenerating(null);
    }
  }

  const current = reports.find(r => r.date === selectedDate) || reports[0] || null;

  function formatDate(d: string): string {
    return new Date(d).toLocaleDateString("de-DE", {
      weekday: "long", day: "2-digit", month: "2-digit"
    });
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] p-4 md:p-6 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <ArrowLeft size={18} />
          </Link>
          <div>
            <h1 className="text-lg font-bold text-[var(--text-primary)]">Briefing</h1>
            <p className="text-xs text-[var(--text-muted)]">
              Pre-Market 08:00 · After-Market 22:15 CET
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={triggerPreMarket}
            disabled={generating !== null}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-40"
          >
            {generating === "pre"
              ? <RefreshCw size={12} className="animate-spin" />
              : <Sun size={12} />}
            Pre-Market
          </button>
          <button
            onClick={triggerAfterMarket}
            disabled={generating !== null}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-40"
          >
            {generating === "after"
              ? <RefreshCw size={12} className="animate-spin" />
              : <Moon size={12} />}
            After-Market
          </button>
          <button
            onClick={triggerSessionPlan}
            disabled={generating !== null}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-40"
          >
            {generating === "plan"
              ? <RefreshCw size={12} className="animate-spin" />
              : <Zap size={12} className="text-[var(--accent-blue)]" />}
            Session Plan
          </button>
        </div>
      </div>

      {/* Datums-Navigation */}
      {reports.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {reports.map(r => (
            <button
              key={r.date}
              onClick={() => setSelectedDate(r.date)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                r.date === selectedDate
                  ? "bg-[var(--accent-blue)] text-white"
                  : "border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
              }`}
            >
              {formatDate(r.date)}
              <span className="ml-1.5 opacity-60">
                {[r.pre_market ? "☀" : "", r.after_market ? "🌙" : "", r.session_plan ? "⚡" : ""].filter(Boolean).join("")}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Reports für gewähltes Datum */}
      {loading ? (
        <div className="flex items-center gap-2 text-[var(--text-muted)] text-sm">
          <RefreshCw size={14} className="animate-spin" />
          Lade Briefings…
        </div>
      ) : current ? (
        <div className="space-y-4">
          {/* Session Plan */}
          {current.session_plan && (
            <div className="card border-l-4 border-l-[var(--accent-blue)]">
              <div
                className="flex items-center justify-between p-4 cursor-pointer"
                onClick={() => setExpanded(prev => ({ ...prev, plan: !prev.plan }))}
              >
                <div className="flex items-center gap-2">
                  <Zap size={13} className="text-[var(--accent-blue)]" />
                  <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--accent-blue)]">
                    Session Plan
                  </p>
                  {current.session_plan_at && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {new Date(current.session_plan_at).toLocaleTimeString(
                        "de-DE", { hour: "2-digit", minute: "2-digit" }
                      )} Uhr
                    </span>
                  )}
                </div>
                {expanded.plan
                  ? <ChevronUp size={14} className="text-[var(--text-muted)]" />
                  : <ChevronDown size={14} className="text-[var(--text-muted)]" />}
              </div>
              {expanded.plan && (
                <div className="px-4 pb-4 border-t border-[var(--border)] pt-3">
                  <div className="whitespace-pre-wrap text-sm text-[var(--text-primary)] leading-relaxed font-mono">
                    {current.session_plan}
                  </div>
                </div>
              )}
            </div>
          )}
          <ReportBlock
            title={`Pre-Market · ${formatDate(current.date)}`}
            report={current.pre_market}
            icon={<Sun size={13} className="text-amber-400" />}
            accentClass="border-l-amber-500"
          />
          <ReportBlock
            title={`After-Market · ${formatDate(current.date)}`}
            report={current.after_market}
            icon={<Moon size={13} className="text-[var(--accent-blue)]" />}
            accentClass="border-l-[var(--accent-blue)]"
          />
        </div>
      ) : (
        <div className="card p-12 text-center">
          <p className="text-sm text-[var(--text-muted)]">
            Noch keine Briefings vorhanden. Pre-Market oder After-Market manuell generieren.
          </p>
        </div>
      )}
    </div>
  );
}
