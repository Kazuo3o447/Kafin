"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, RefreshCw, TrendingUp, TrendingDown,
  Minus, BookmarkPlus, BookmarkMinus, Sparkles,
  Calendar, AlertTriangle, ChevronUp, ChevronDown,
  Clock, BarChart2, Activity, DollarSign, Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { cacheGet, cacheSet, cacheInvalidate } from "@/lib/clientCache";

// ── Typen ────────────────────────────────────────────────────
type ResearchData = {
  ticker: string;
  resolved_ticker?: string;
  was_resolved?: boolean;
  resolution_note?: string;
  data_quality?: "good" | "partial" | "poor" | "unknown";
  available_fields?: number;
  core_fields_available?: number;
  data_sufficient_for_ai?: boolean;
  ai_blocked_reason?: string;
  company_name: string;
  sector: string | null;
  industry: string | null;
  fetched_at: string;
  price: number | null;
  change_pct: number | null;
  price_change_30d: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  ps_ratio: number | null;
  peg_ratio: number | null;
  ev_ebitda: number | null;
  market_cap: number | null;
  beta: number | null;
  dividend_yield: number | null;
  revenue_ttm: number | null;
  eps_ttm: number | null;
  roe: number | null;
  roa: number | null;
  debt_equity: number | null;
  fcf_yield: number | null;
  current_ratio: number | null;
  analyst_target: number | null;
  analyst_target_high: number | null;
  analyst_target_low: number | null;
  analyst_recommendation: string | null;
  number_of_analysts: number | null;
  rsi: number | null;
  trend: string | null;
  sma_50: number | null;
  sma_200: number | null;
  above_sma50: boolean | null;
  above_sma200: boolean | null;
  sma50_distance_pct: number | null;
  sma200_distance_pct: number | null;
  support: number | null;
  resistance: number | null;
  distance_52w_high_pct: number | null;
  iv_atm: number | null;
  put_call_ratio: number | null;
  expected_move_pct: number | null;
  expected_move_usd: number | null;
  short_interest_pct: number | null;
  days_to_cover: number | null;
  squeeze_risk: string | null;
  insider_buys: number;
  insider_sells: number;
  insider_buy_value: number;
  insider_sell_value: number;
  insider_assessment: string;
  earnings_date: string | null;
  report_timing: string | null;
  earnings_countdown: number | null;
  earnings_today: boolean;
  eps_consensus: number | null;
  revenue_consensus: number | null;
  beats_of_8: number | null;
  avg_surprise_pct: number | null;
  last_surprise_pct: number | null;
  last_beat: boolean | null;
  quarterly_history: Array<{
    quarter: string;
    eps_actual: number | null;
    eps_consensus: number | null;
    surprise_pct: number | null;
    reaction_1d: number | null;
  }>;
  news_bullets: Array<{
    text: string;
    sentiment: number;
    is_material: boolean;
    category: string;
    date: string;
  }>;
  is_watchlist: boolean;
  web_prio: number | null;
  last_audit: {
    date: string;
    recommendation: string;
    opportunity_score: number;
    torpedo_score: number;
    report_text: string;
  } | null;
};

// ── Hilfsfunktionen ──────────────────────────────────────────
const fmt = {
  pct: (v: number | null, decimals = 1) =>
    v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`,
  num: (v: number | null, decimals = 2) =>
    v == null ? "—" : v.toFixed(decimals),
  usd: (v: number | null) =>
    v == null ? "—" : `$${v.toFixed(2)}`,
  cap: (v: number | null) => {
    if (v == null) return "—";
    if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
    if (v >= 1e9)  return `$${(v / 1e9).toFixed(2)}B`;
    if (v >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`;
    return `$${v.toFixed(0)}`;
  },
  date: (s: string | null) => {
    if (!s) return "—";
    try { return new Date(s).toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" }); }
    catch { return s; }
  },
};

function colorPct(v: number | null) {
  if (v == null) return "text-[var(--text-muted)]";
  return v >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]";
}

function PctBadge({ value }: { value: number | null }) {
  if (value == null) return <span className="text-[var(--text-muted)]">—</span>;
  return (
    <span className={`font-mono font-semibold ${colorPct(value)}`}>
      {value >= 0 ? <ChevronUp size={12} className="inline" /> : <ChevronDown size={12} className="inline" />}
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

function StatCell({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded-lg bg-[var(--bg-tertiary)] px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)] mb-1">{label}</p>
      <p className="text-sm font-semibold text-[var(--text-primary)] font-mono">{value}</p>
      {sub && <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{sub}</p>}
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--bg-elevated)] ${className}`} />;
}

// ── Hauptkomponente ───────────────────────────────────────────
export default function ResearchDashboard() {
  const { ticker } = useParams() as { ticker: string };
  const tickerUpper = ticker.toUpperCase();

  const [data, setData] = useState<ResearchData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiReport, setAiReport] = useState<string | null>(null);
  const [aiDate, setAiDate] = useState<string | null>(null);

  const [onWatchlist, setOnWatchlist] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [overrideTicker, setOverrideTicker] = useState("");
  const [showOverrideInput, setShowOverrideInput] = useState(false);

  // Letzte 5 Suchen speichern
  useEffect(() => {
    if (!tickerUpper) return;
    try {
      const raw = localStorage.getItem("kafin_recent_research") || "[]";
      const recent: string[] = JSON.parse(raw);
      const updated = [tickerUpper, ...recent.filter(t => t !== tickerUpper)].slice(0, 5);
      localStorage.setItem("kafin_recent_research", JSON.stringify(updated));
    } catch {}
  }, [tickerUpper]);

  const loadData = useCallback(async (forceRefresh = false) => {
    if (forceRefresh) {
      cacheInvalidate(`research:${tickerUpper}`);
    }
    
    if (!forceRefresh) {
      const cached = cacheGet<ResearchData>(`research:${tickerUpper}`);
      if (cached) {
        setData(cached);
        setOnWatchlist(cached.is_watchlist);
        setLoading(false);
        if (cached.last_audit) {
          setAiReport(cached.last_audit.report_text);
          setAiDate(cached.last_audit.date);
        }
        return;
      }
    }

    if (forceRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const result = await api.getResearchDashboard(
        tickerUpper,
        forceRefresh,
        overrideTicker || undefined,
      );
      setData(result);
      setOnWatchlist(result.is_watchlist);
      cacheSet(`research:${tickerUpper}`, result, 600);
      if (result.last_audit) {
        setAiReport(result.last_audit.report_text);
        setAiDate(result.last_audit.date);
      }
    } catch (e: any) {
      setError(e?.message || "Daten konnten nicht geladen werden");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [tickerUpper]);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleAuditReport() {
    setAiLoading(true);
    setAiReport(null);
    try {
      const result = await api.generateAuditReport(tickerUpper);
      const text = result.report || result.message || "Report generiert.";
      setAiReport(text);
      setAiDate(new Date().toISOString());
      // Cache sicher aktualisieren
      if (data) {
        const updatedData = {
          ...data,
          last_audit: {
            date: new Date().toISOString(),
            recommendation: data.last_audit?.recommendation || "",
            opportunity_score: data.last_audit?.opportunity_score || 0,
            torpedo_score: data.last_audit?.torpedo_score || 0,
            report_text: text
          }
        };
        cacheSet(`research:${tickerUpper}`, updatedData, 600);
      }
    } catch {
      setAiReport("Report-Generierung fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setAiLoading(false);
    }
  }

  async function handleWatchlist() {
    if (!data) return;
    setWatchlistLoading(true);
    try {
      if (onWatchlist) {
        await api.removeTicker(tickerUpper);
        setOnWatchlist(false);
      } else {
        await api.addTicker({
          ticker: tickerUpper,
          company_name: data.company_name || tickerUpper,
          sector: data.sector || "Unknown",
          notes: "",
        });
        setOnWatchlist(true);
      }
    } catch (e) {
      console.error("Watchlist error", e);
    } finally {
      setWatchlistLoading(false);
    }
  }

  // ── Earnings-Banner ───────────────────────────────────────
  const earningsBanner = data?.earnings_countdown != null && data.earnings_countdown <= 7 ? (
    <div className={`rounded-xl px-4 py-3 flex items-center gap-3 ${
      data.earnings_today
        ? "bg-[var(--accent-amber)]/15 border border-[var(--accent-amber)]/40"
        : "bg-[var(--accent-blue)]/10 border border-[var(--accent-blue)]/30"
    }`}>
      <Calendar size={16} className={data.earnings_today ? "text-[var(--accent-amber)]" : "text-[var(--accent-blue)]"} />
      <span className={`text-sm font-semibold ${data.earnings_today ? "text-[var(--accent-amber)]" : "text-[var(--accent-blue)]"}`}>
        {data.earnings_today ? "⚡ Earnings HEUTE" : `📅 Earnings in ${data.earnings_countdown} Tagen`}
        {data.report_timing === "pre_market" ? " · Pre-Market 🌅" : data.report_timing === "after_hours" ? " · After-Hours 🌙" : ""}
      </span>
      {data.eps_consensus != null && (
        <span className="ml-auto text-xs text-[var(--text-secondary)] font-mono">
          EPS-Konsens: ${data.eps_consensus.toFixed(2)}
          {data.revenue_consensus != null && ` · Rev: ${fmt.cap(data.revenue_consensus)}`}
        </span>
      )}
    </div>
  ) : null;

  {/* ── Resolution-Banner ────────────────────────────────── */}
  {data?.was_resolved && data.resolution_note && (
    <div className="rounded-xl border border-[var(--accent-amber)]/40
                    bg-[var(--accent-amber)]/10 px-4 py-3
                    flex items-center gap-3">
      <span className="text-[var(--accent-amber)] text-sm">⚡</span>
      <span className="text-sm text-[var(--accent-amber)]">
        <strong>Automatisch aufgelöst:</strong> {data.resolution_note}
      </span>
    </div>
  )}

  {/* ── Datenqualitäts-Warnung ────────────────────────────── */}
  {data && data.data_quality === "poor" && (
    <div className="rounded-xl border border-[var(--accent-red)]/40
                    bg-[var(--accent-red)]/10 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle size={16} className="text-[var(--accent-red)]" />
        <span className="text-sm font-semibold text-[var(--accent-red)]">
          Begrenzte Datenverfügbarkeit ({data.available_fields ?? 0} Kernfelder)
        </span>
      </div>
      <p className="text-xs text-[var(--text-secondary)]">
        {data.resolution_note ||
          "Für diesen Ticker sind kaum Fundamentaldaten verfügbar. " +
          "Versuche den primären Börsenticker."}
      </p>

      {/* Override-Input */}
      {!showOverrideInput ? (
        <button
          onClick={() => setShowOverrideInput(true)}
          className="text-xs text-[var(--accent-blue)] hover:underline"
        >
          + Alternativen Ticker eingeben
        </button>
      ) : (
        <div className="flex gap-2">
          <input
            type="text"
            value={overrideTicker}
            onChange={e => setOverrideTicker(e.target.value.toUpperCase())}
            placeholder="z.B. VOW3.DE"
            className="flex-1 rounded-lg border border-[var(--border)]
                       bg-[var(--bg-secondary)] px-3 py-1.5 text-sm
                       font-mono text-[var(--text-primary)]
                       focus:border-[var(--accent-blue)] outline-none"
          />
          <button
            onClick={() => { setShowOverrideInput(false); loadData(true); }}
            disabled={!overrideTicker.trim()}
            className="rounded-lg bg-[var(--accent-blue)] px-3 py-1.5
                       text-xs font-semibold text-white
                       hover:opacity-90 disabled:opacity-40"
          >
            Laden
          </button>
          <button
            onClick={() => { setOverrideTicker(""); setShowOverrideInput(false); }}
            className="rounded-lg border border-[var(--border)]
                       px-3 py-1.5 text-xs text-[var(--text-muted)]"
          >
            Abbrechen
          </button>
        </div>
      )}
    </div>
  )}

  // ── Loading Skeleton ──────────────────────────────────────
  if (loading) return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-24 w-full" />
      <div className="grid grid-cols-4 gap-3">
        {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-16" />)}
      </div>
      <Skeleton className="h-48 w-full" />
    </div>
  );

  if (error) return (
    <div className="flex h-64 flex-col items-center justify-center gap-4">
      <AlertTriangle size={32} className="text-[var(--accent-red)]" />
      <p className="text-[var(--text-secondary)]">{error}</p>
      <button onClick={() => loadData(true)}
        className="rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm text-white">
        Erneut versuchen
      </button>
    </div>
  );

  if (!data) return null;

  const uptrend = data.trend === "uptrend";
  const downtrend = data.trend === "downtrend";

  return (
    <div className="space-y-5 pb-12">

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/research"
            className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-2">
            <ArrowLeft size={13} /> Research
          </Link>
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl font-bold font-mono text-[var(--text-primary)]">{data.ticker}</h1>
            {data.price != null && (
              <span className="text-2xl font-mono text-[var(--text-primary)]">${data.price.toFixed(2)}</span>
            )}
            <PctBadge value={data.change_pct} />
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">
            {data.company_name}
            {data.sector && <span className="mx-2 text-[var(--text-muted)]">·</span>}
            {data.sector && <span className="text-[var(--text-muted)]">{data.sector}</span>}
            {data.industry && <span className="text-[var(--text-muted)]"> / {data.industry}</span>}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)]
                       px-3 py-2 text-xs text-[var(--text-secondary)]
                       hover:bg-[var(--bg-tertiary)] disabled:opacity-40 transition-all"
          >
            <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "Lädt..." : "Aktualisieren"}
          </button>
          <button
            onClick={handleWatchlist}
            disabled={watchlistLoading}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs
                       font-medium transition-all disabled:opacity-40 ${
              onWatchlist
                ? "bg-[var(--accent-green)]/15 text-[var(--accent-green)] border border-[var(--accent-green)]/30"
                : "border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
            }`}
          >
            {onWatchlist ? <BookmarkMinus size={12} /> : <BookmarkPlus size={12} />}
            {onWatchlist ? "Auf Watchlist" : "Zur Watchlist"}
          </button>
        </div>
      </div>

      {/* ── Timestamp ─────────────────────────────────────── */}
      <p className="text-[10px] text-[var(--text-muted)]">
        <Clock size={10} className="inline mr-1" />
        Stand: {fmt.date(data.fetched_at)} {new Date(data.fetched_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
      </p>

      {/* ── Earnings-Banner ───────────────────────────────── */}
      {earningsBanner}

      {/* ══════════════════════════════════════════════════════
          OBERER TEIL: SOFORT-ÜBERBLICK
      ══════════════════════════════════════════════════════ */}

      {/* Block 1: Preis & Performance */}
      <div className="card p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
          Preis & Performance
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
          <StatCell label="30T Performance" value={<PctBadge value={data.price_change_30d} />} />
          <StatCell label="52W Hoch" value={fmt.usd(data.fifty_two_week_high)} sub={data.distance_52w_high_pct != null ? `${data.distance_52w_high_pct.toFixed(1)}% entfernt` : undefined} />
          <StatCell label="52W Tief" value={fmt.usd(data.fifty_two_week_low)} />
          <StatCell label="Market Cap" value={fmt.cap(data.market_cap)} />
          <StatCell label="Beta" value={fmt.num(data.beta)} sub="Marktkorrelation" />
          <StatCell label="Div. Yield" value={data.dividend_yield ? `${(data.dividend_yield * 100).toFixed(2)}%` : "—"} />
        </div>
      </div>

      {/* Block 2: Bewertung */}
      <div className="card p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
          Bewertung
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          <StatCell label="P/E (TTM)" value={fmt.num(data.pe_ratio)} />
          <StatCell label="Forward P/E" value={fmt.num(data.forward_pe)} />
          <StatCell label="PEG Ratio" value={
            <span className={
              data.peg_ratio == null ? "text-[var(--text-muted)]"
              : data.peg_ratio < 0 ? "text-gray-400"  // Negative earnings
              : data.peg_ratio < 1 ? "text-[var(--accent-green)]"
              : data.peg_ratio > 2 ? "text-[var(--accent-red)]"
              : "text-[var(--accent-amber)]"
            }>
              {fmt.num(data.peg_ratio)}
            </span>
          } sub={data.peg_ratio != null ? (data.peg_ratio < 0 ? "negative earnings" : data.peg_ratio < 1 ? "günstig" : data.peg_ratio > 2 ? "teuer" : "fair") : undefined} />
          <StatCell label="P/S Ratio" value={fmt.num(data.ps_ratio)} />
          <StatCell label="EV/EBITDA" value={fmt.num(data.ev_ebitda)} />
          <StatCell label="ROE" value={data.roe != null ? `${data.roe.toFixed(1)}%` : "—"} />
          <StatCell label="ROA" value={data.roa != null ? `${data.roa.toFixed(1)}%` : "—"} />
          <StatCell label="Debt/Equity" value={fmt.num(data.debt_equity)} />
          <StatCell label="FCF Yield" value={data.fcf_yield != null ? `${data.fcf_yield.toFixed(2)}%` : "—"} />
          <StatCell label="Current Ratio" value={fmt.num(data.current_ratio)} />
          <StatCell label="EPS TTM" value={fmt.usd(data.eps_ttm)} />
          <StatCell label="Revenue TTM" value={fmt.cap(data.revenue_ttm)} />
        </div>
      </div>

      {/* Block 3: Technisches Bild + Analyst */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
            Technisches Bild
          </p>
          <div className="grid grid-cols-2 gap-2">
            <StatCell label="RSI (14)" value={
              <span className={data.rsi == null ? "text-[var(--text-muted)]" : data.rsi > 70 ? "text-[var(--accent-red)]" : data.rsi < 30 ? "text-[var(--accent-green)]" : "text-[var(--text-primary)]"}>
                {fmt.num(data.rsi, 1)}
              </span>
            } sub={data.rsi != null ? (data.rsi > 70 ? "überkauft" : data.rsi < 30 ? "überverkauft" : "neutral") : undefined} />
            <StatCell label="Trend" value={
              <span className={uptrend ? "text-[var(--accent-green)]" : downtrend ? "text-[var(--accent-red)]" : "text-[var(--accent-amber)]"}>
                {uptrend ? "↑ Aufwärts" : downtrend ? "↓ Abwärts" : "→ Seitwärts"}
              </span>
            } />
            <StatCell label="SMA 50" value={fmt.usd(data.sma_50)} sub={data.above_sma50 != null ? (data.above_sma50 ? "✓ darüber" : "✗ darunter") : undefined} />
            <StatCell label="SMA 200" value={fmt.usd(data.sma_200)} sub={data.above_sma200 != null ? (data.above_sma200 ? "✓ darüber" : "✗ darunter") : undefined} />
            <StatCell label="Support" value={fmt.usd(data.support)} />
            <StatCell label="Resistance" value={fmt.usd(data.resistance)} />
          </div>
        </div>

        <div className="card p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
            Analyst & Options
          </p>
          <div className="grid grid-cols-2 gap-2">
            <StatCell label="Kursziel Ø" value={fmt.usd(data.analyst_target)} sub={
              data.analyst_target && data.price
                ? `${fmt.pct(((data.analyst_target - data.price) / data.price) * 100)} Upside` 
                : undefined
            } />
            <StatCell label="Empfehlung" value={
              <span className={
                data.analyst_recommendation?.includes("buy") ? "text-[var(--accent-green)]"
                : data.analyst_recommendation?.includes("sell") ? "text-[var(--accent-red)]"
                : "text-[var(--accent-amber)]"
              }>
                {data.analyst_recommendation?.toUpperCase() || "—"}
              </span>
            } sub={data.number_of_analysts ? `${data.number_of_analysts} Analysten` : undefined} />
            <StatCell label="IV (ATM)" value={data.iv_atm != null ? `${data.iv_atm.toFixed(1)}%` : "—"} />
            <StatCell label="Put/Call" value={fmt.num(data.put_call_ratio)} />
            <StatCell label="Exp. Move" value={
              data.expected_move_pct != null
                ? `±${data.expected_move_pct.toFixed(1)}%` 
                : "—"
            } sub={data.expected_move_usd != null ? `±$${data.expected_move_usd.toFixed(2)}` : undefined} />
            <StatCell label="Short Int." value={data.short_interest_pct != null ? `${data.short_interest_pct.toFixed(1)}%` : "—"} sub={data.squeeze_risk ? `Squeeze: ${data.squeeze_risk}` : undefined} />
          </div>
        </div>
      </div>

      {/* Block 4: Earnings-Historie + Insider */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
            Earnings-Historie
          </p>
          <div className="mb-3 flex gap-4 text-sm">
            <span className="text-[var(--text-secondary)]">Beat-Rate: <span className="font-semibold text-[var(--text-primary)]">{data.beats_of_8 ?? "—"}/8</span></span>
            <span className="text-[var(--text-secondary)]">Ø Surprise: <span className={`font-semibold ${colorPct(data.avg_surprise_pct)}`}>{fmt.pct(data.avg_surprise_pct)}</span></span>
            <span className="text-[var(--text-secondary)]">Letzter: <span className={`font-semibold ${colorPct(data.last_surprise_pct)}`}>{fmt.pct(data.last_surprise_pct)}</span></span>
          </div>
          {data.quarterly_history.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="py-1.5 text-left text-[var(--text-muted)]">Quartal</th>
                    <th className="py-1.5 text-right text-[var(--text-muted)]">EPS</th>
                    <th className="py-1.5 text-right text-[var(--text-muted)]">Konsens</th>
                    <th className="py-1.5 text-right text-[var(--text-muted)]">Surprise</th>
                    <th className="py-1.5 text-right text-[var(--text-muted)]">1T</th>
                  </tr>
                </thead>
                <tbody>
                  {data.quarterly_history.map((q, i) => (
                    <tr key={i} className="border-b border-[var(--border)]/50">
                      <td className="py-1.5 text-[var(--text-secondary)] font-mono">{q.quarter}</td>
                      <td className="py-1.5 text-right font-mono text-[var(--text-primary)]">{fmt.usd(q.eps_actual)}</td>
                      <td className="py-1.5 text-right font-mono text-[var(--text-muted)]">{fmt.usd(q.eps_consensus)}</td>
                      <td className={`py-1.5 text-right font-mono font-semibold ${colorPct(q.surprise_pct)}`}>{fmt.pct(q.surprise_pct)}</td>
                      <td className={`py-1.5 text-right font-mono ${colorPct(q.reaction_1d)}`}>{fmt.pct(q.reaction_1d)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">Keine Historien-Daten verfügbar</p>
          )}
        </div>

        <div className="card p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
            Insider-Aktivität (90 Tage)
          </p>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-[var(--accent-green)]" />
                <span className="text-sm text-[var(--text-secondary)]">Käufe</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-semibold text-[var(--accent-green)]">{data.insider_buys} Transaktionen</span>
                <p className="text-xs text-[var(--text-muted)]">{fmt.cap(data.insider_buy_value)}</p>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-[var(--accent-red)]" />
                <span className="text-sm text-[var(--text-secondary)]">Verkäufe</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-semibold text-[var(--accent-red)]">{data.insider_sells} Transaktionen</span>
                <p className="text-xs text-[var(--text-muted)]">{fmt.cap(data.insider_sell_value)}</p>
              </div>
            </div>
            <div className={`rounded-lg px-3 py-2 text-xs font-medium ${
              data.insider_assessment === "bearish" ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
              : data.insider_assessment === "bullish" ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
              : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
            }`}>
              Einordnung: {data.insider_assessment?.toUpperCase() || "NEUTRAL"}
            </div>
          </div>

          {/* News-Stichpunkte */}
          {data.news_bullets.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
                Aktuelle News
              </p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {data.news_bullets.slice(0, 6).map((n, i) => (
                  <div key={i} className={`rounded px-2 py-1.5 text-xs ${n.is_material ? "bg-[var(--accent-red)]/10 border-l-2 border-[var(--accent-red)]" : "bg-[var(--bg-tertiary)]"}`}>
                    <span className={`mr-1 font-semibold ${n.sentiment > 0.3 ? "text-[var(--accent-green)]" : n.sentiment < -0.3 ? "text-[var(--accent-red)]" : "text-[var(--text-muted)]"}`}>
                      {n.sentiment > 0.3 ? "▲" : n.sentiment < -0.3 ? "▼" : "●"}
                    </span>
                    {n.text}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          UNTERER TEIL: KI-ANALYSE
      ══════════════════════════════════════════════════════ */}
      <div className="card-accent p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-[var(--accent-blue)]" />
            <p className="text-sm font-semibold text-[var(--text-primary)]">KI-Analyse & Handlungsempfehlung</p>
          </div>
          <div className="flex items-center gap-2">
            {aiDate && (
              <span className="text-[10px] text-[var(--text-muted)]">
                <Clock size={10} className="inline mr-1" />
                {fmt.date(aiDate)} {new Date(aiDate).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            <button
              onClick={handleAuditReport}
              disabled={aiLoading || data?.data_sufficient_for_ai === false}
              title={data?.data_sufficient_for_ai === false
                ? data?.ai_blocked_reason
                : undefined}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm
                         font-semibold transition-all disabled:opacity-50 ${
                data?.data_sufficient_for_ai === false
                  ? "border border-[var(--accent-red)]/40 text-[var(--accent-red)] cursor-not-allowed"
                  : aiReport
                  ? "border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                  : "bg-[var(--accent-blue)] text-white hover:opacity-90"
              }`}
            >
              {aiLoading ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  Analysiert... (30-60s)
                </>
              ) : aiReport ? (
                <>
                  <RefreshCw size={14} />
                  Neu analysieren
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  KI-Analyse starten
                </>
              )}
            </button>
          </div>
        </div>

        {!aiReport && !aiLoading && (
          <div className="rounded-xl border border-dashed border-[var(--border)] py-12 text-center">
            <Sparkles size={24} className="mx-auto mb-3 text-[var(--text-muted)]" />
            <p className="text-sm text-[var(--text-muted)]">
              Klicke "KI-Analyse starten" für eine vollständige Einschätzung
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Opportunity/Torpedo-Score · Handlungsempfehlung · Konkrete Levels
            </p>
          </div>
        )}

        {aiLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
            <Skeleton className="h-4 w-full mt-4" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {!aiReport && !aiLoading && data?.data_sufficient_for_ai === false && (
          <div className="rounded-xl border border-dashed
                          border-[var(--accent-red)]/40 py-8 text-center px-4">
            <AlertTriangle size={20} className="mx-auto mb-2
                                               text-[var(--accent-red)]" />
            <p className="text-sm font-semibold text-[var(--accent-red)] mb-1">
              Analyse nicht möglich
            </p>
            <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
              {data.ai_blocked_reason}
            </p>
          </div>
        )}

        {aiReport && !aiLoading && (
          <div className="prose-sm max-w-none">
            <div className="whitespace-pre-wrap text-sm text-[var(--text-primary)] leading-relaxed max-h-[500px] overflow-y-auto pr-2">
              {aiReport}
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
