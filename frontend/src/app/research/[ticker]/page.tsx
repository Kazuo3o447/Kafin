"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
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
import { PriceRangeBar } from "@/components/visualizations/PriceRangeBar";
import { VolumeProfile } from "@/components/visualizations/VolumeProfile";
import { PEGGauge } from "@/components/visualizations/PEGGauge";
import { ChartAnalysisSection } from "@/components/ChartAnalysisSection";

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
  is_etf?: boolean;
  is_index?: boolean;
  asset_type?: "stock" | "etf" | "index";
  company_name: string;
  sector: string | null;
  industry: string | null;
  fetched_at: string;
  price: number | null;
  change_pct: number | null;
  price_change_30d: number | null;
  price_change_5d?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  pre_market_price?: number | null;
  post_market_price?: number | null;
  pre_market_change?: number | null;
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
  sma_20?: number | null;
  atr_14?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_histogram?: number | null;
  macd_bullish?: boolean | null;
  obv_trend?: string | null;
  rvol?: number | null;
  float_shares?: number | null;
  avg_volume?: number | null;
  bid_ask_spread?: number | null;
  iv_atm: number | null;
  put_call_ratio: number | null;
  expected_move_pct: number | null;
  expected_move_usd?: number | null;
  max_pain?: number | null;
  options_oi_url?: string;
  
  // Twelve Data Erweiterungen
  adx_14?: number | null;
  adx_plus_di?: number | null;
  adx_minus_di?: number | null;
  adx_trend_strength?: "strong" | "moderate" | "weak" | null;
  stoch_k?: number | null;
  stoch_d?: number | null;
  stoch_signal?: "bullish_cross" | "bearish_cross" | "oversold" | "overbought" | "neutral" | null;
  iv_percentile?: number | null;
  td_enriched?: boolean;
  
  short_interest_pct?: number | null;
  days_to_cover: number | null;
  squeeze_risk: string | null;
  insider_buys: number;
  insider_sells: number;
  insider_buy_value: number;
  insider_sell_value: number;
  insider_assessment: string;
  earnings_date: string | null;
  report_timing?: string | null;
  earnings_countdown: number | null;
  earnings_today: boolean;
  eps_consensus?: number | null;
  revenue_consensus?: number | null;
  beats_of_8?: number | null;
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
    source?: string;
    url?: string;
  }>;
  finbert_sentiment?: number | null;
  sentiment_label?: string | null;
  sentiment_trend?: string | null;
  sentiment_has_material?: boolean | null;
  sentiment_count?: number | null;
  sentiment_divergence?: boolean | null;
  market_sentiment_avg?: number | null;
  sentiment_vs_market?: number | null;
  market_sentiment_detail?: Record<string,{
    score: number; count: number; label: string
  }> | null;
  reddit_sentiment?: {
    score: number | null;
    mentions: number;
    label: string | null;
  } | null;
  fear_greed?: {
    score: number | null;
    label: string | null;
  } | null;
  sector_earnings_upcoming?: Array<{
    ticker: string;
    date: string | null;
    timing: string | null;
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
  opportunity_score?: number | null;
  torpedo_score?: number | null;
  recommendation?: string | null;
  recommendation_label?: string | null;
  recommendation_reason?: string | null;
  score_breakdown?: {
    opportunity: Record<string, number>;
    torpedo: Record<string, number>;
  } | null;
  relative_strength?: {
    vs_spy_1d: number | null;
    vs_spy_5d: number | null;
    vs_spy_1m: number | null;
    vs_sector_1d: number | null;
    vs_sector_5d: number | null;
    vs_sector_1m: number | null;
    spy_1d: number | null;
    spy_5d: number | null;
    spy_1m: number | null;
    sector_etf: string | null;
    sector_1d: number | null;
    sector_5d: number | null;
    sector_1m: number | null;
    label: string;
    signal: "bullish" | "bearish" | "neutral";
  } | null;
  company_profile?: {
    ceo?: string | null;
    employees?: number | null;
    description?: string | null;
    website?: string | null;
    ipo_date?: string | null;
    country?: string | null;
    exchange?: string | null;
    peers?: string[];
  } | null;
  exchange?: string | null;
  peers?: string[];
};

type TradeReviewDecision = {
  ticker: string;
  recommendation: string;
  recommendation_label?: string | null;
  reasoning?: string | null;
  confidence?: number | null;
  opportunity_score?: number | null;
  torpedo_score?: number | null;
  prompt_text?: string | null;
  decision_text?: string | null;
  model_used?: string | null;
  key_bull_points?: string[];
  key_risks?: string[];
  execution_note?: string | null;
  top_drivers?: Array<{ key: string; label: string; value: number }>;
  top_risks?: Array<{ key: string; label: string; value: number }>;
  raw_data?: Record<string, unknown>;
};

type FilingDiffData = {
  ticker: string;
  available: boolean;
  filing_type?: string;
  overall_signal?: "BULLISH" | "BEARISH"
                  | "GEMISCHT" | "NEUTRAL";
  diff_text?: string;
  model?: string;
  model_used?: string;
  current_period?: string;
  prev_period?: string;
  chars_analyzed?: number;
  error?: string;
};

type ScoreDeltaData = {
  yesterday: {
    opportunity_score: number | null;
    torpedo_score: number | null;
  } | null;
  last_week: {
    opportunity_score: number | null;
    torpedo_score: number | null;
  } | null;
};

type ChatMsg = {
  role: "user" | "assistant";
  content: string;
};

type PeerItem = {
  ticker: string;
  name: string;
  price: number | null;
  change_5d_pct: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  ps_ratio: number | null;
  market_cap_b: number | null;
  rvol: number | null;
};

type PeerComparisonData = {
  main: string;
  peers: PeerItem[];
};

type ChartAnalysisData = {
  ticker: string;
  price: number;
  rsi: number | null;
  trend: string;
  volume_trend: string;
  sma_50: number | null;
  sma_200: number | null;
  support_levels: Array<{
    price: number;
    strength: "strong" | "moderate" | "weak";
    label: string;
  }>;
  resistance_levels: Array<{
    price: number;
    strength: "strong" | "moderate" | "weak";
    label: string;
  }>;
  entry_zone: {
    low: number;
    high: number;
  };
  stop_loss: number;
  target_1: number;
  target_2: number;
  analysis_text: string;
  bias: "bullish" | "bearish" | "neutral";
  key_risk: string;
  why_entry?: string;
  why_stop?: string;
  trend_context?: string;
  floor_scenario?: string;
  turnaround_conditions?: string;
  falling_knife_risk?: "low" | "medium" | "high";
  error?: boolean;
} | null;

type OptionsOiData = {
  ticker: string;
  nearest_max_pain: number | null;
  expirations: Array<{
    expiry: string;
    max_pain: number;
    pcr_oi: number | null;
    total_call_oi: number;
    total_put_oi: number;
    top_oi_strikes: Array<{
      strike: number;
      call_oi: number;
      put_oi: number;
      total_oi: number;
    }>;
    error?: string;
  }>;
};

// ── Hilfsfunktionen ──────────────────────────────────────────
const fmt = {
  pct: (v: number | null, decimals = 1) =>
    v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`,
  num: (v: number | null | undefined, decimals = 2) =>
    v == null ? "—" : v.toFixed(decimals),
  usd: (v: number | null | undefined) =>
    v == null ? "—" : `$${v.toFixed(2)}`,
  cap: (v: number | null | undefined) => {
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

function normalizeResearchData(raw: any): ResearchData {
  const fundamentals = raw?.fundamentals ?? {};
  const technicals = raw?.technicals ?? {};
  const earnings = raw?.earnings ?? {};
  const analyst = raw?.analyst ?? {};
  const sentiment = raw?.sentiment ?? {};
  const smartMoney = raw?.smart_money ?? {};
  const expectedMove = raw?.expected_move ?? {};
  const relativeStrength = raw?.relative_strength ?? null;
  const companyProfile = raw?.company_profile ?? {
    ceo: fundamentals.ceo ?? null,
    employees: fundamentals.employees ?? null,
    description: fundamentals.description ?? null,
    website: fundamentals.website ?? null,
    ipo_date: fundamentals.ipo_date ?? null,
    country: raw?.country ?? null,
    exchange: raw?.exchange ?? null,
    peers: fundamentals.peers ?? raw?.peers ?? [],
  };

  const quarterlyHistorySource = Array.isArray(earnings.quarterly_history)
    ? earnings.quarterly_history
    : Array.isArray(raw?.quarterly_history)
      ? raw.quarterly_history
      : [];

  const quarterlyHistory = quarterlyHistorySource.map((q: any) => ({
    quarter: q?.quarter ?? "",
    eps_actual: q?.eps_actual ?? null,
    eps_consensus: q?.eps_consensus ?? null,
    surprise_pct: q?.surprise_pct ?? null,
    reaction_1d: q?.reaction_1d ?? null,
  }));

  const newsBulletsSource = Array.isArray(raw?.news_bullets)
    ? raw.news_bullets
    : Array.isArray(sentiment.news)
      ? sentiment.news
      : [];

  const newsBullets = newsBulletsSource.map((item: any) => ({
    text: item?.text ?? item?.headline ?? item?.bullet_text ?? "",
    sentiment: Number(item?.sentiment ?? item?.score ?? 0),
    is_material: Boolean(item?.is_material ?? item?.material ?? false),
    category: item?.category ?? "News",
    date: item?.date ?? item?.created_at ?? item?.datetime ?? "",
    source: item?.source,
    url: item?.url,
  }));

  const redditSentiment = sentiment.reddit_sentiment && typeof sentiment.reddit_sentiment === "object"
    ? {
        score: sentiment.reddit_sentiment.score ?? null,
        mentions: sentiment.reddit_sentiment.mentions ?? 0,
        label: sentiment.reddit_sentiment.label ?? null,
      }
    : null;

  const fearGreed = sentiment.fear_greed && typeof sentiment.fear_greed === "object"
    ? {
        score: sentiment.fear_greed.score ?? null,
        label: sentiment.fear_greed.label ?? null,
      }
    : (sentiment.fear_greed_score != null || sentiment.fear_greed_label != null)
      ? {
          score: sentiment.fear_greed_score ?? null,
          label: sentiment.fear_greed_label ?? null,
        }
      : null;

  return {
    ...(raw ?? {}),
    ticker: raw?.ticker ?? raw?.effective_ticker ?? "",
    resolved_ticker: raw?.effective_ticker ?? raw?.resolved_ticker,
    was_resolved: raw?.resolution?.was_resolved ?? raw?.was_resolved,
    resolution_note: raw?.resolution?.resolution_note ?? raw?.resolution_note,
    data_quality: raw?.resolution?.data_quality ?? raw?.data_quality ?? "unknown",
    available_fields: raw?.resolution?.available_fields ?? raw?.available_fields,
    core_fields_available: raw?.core_fields_available ?? raw?.resolution?.core_fields_available,
    data_sufficient_for_ai: raw?.data_sufficient_for_ai ?? raw?.ai?.data_sufficient_for_ai,
    ai_blocked_reason: raw?.ai_blocked_reason ?? raw?.ai?.blocked_reason,
    is_etf: raw?.is_etf ?? raw?.asset_type === "etf",
    is_index: raw?.is_index ?? raw?.asset_type === "index",
    asset_type: raw?.asset_type ?? (raw?.is_etf ? "etf" : raw?.is_index ? "index" : "stock"),
    company_name: raw?.company_name ?? raw?.name ?? raw?.ticker ?? raw?.effective_ticker ?? "",
    sector: raw?.sector ?? fundamentals.sector ?? null,
    industry: raw?.industry ?? fundamentals.industry ?? null,
    fetched_at: raw?.fetched_at ?? raw?.timestamp ?? new Date().toISOString(),
    price: raw?.price ?? null,
    change_pct: raw?.change_pct ?? null,
    price_change_30d: raw?.price_change_30d ?? raw?.change_1m_pct ?? null,
    price_change_5d: raw?.price_change_5d ?? raw?.change_5d_pct ?? null,
    fifty_two_week_high: raw?.fifty_two_week_high ?? technicals.fifty_two_week_high ?? null,
    fifty_two_week_low: raw?.fifty_two_week_low ?? technicals.fifty_two_week_low ?? null,
    pre_market_price: raw?.pre_market_price ?? null,
    post_market_price: raw?.post_market_price ?? null,
    pre_market_change: raw?.pre_market_change ?? null,
    pe_ratio: raw?.pe_ratio ?? fundamentals.pe_ratio ?? null,
    forward_pe: raw?.forward_pe ?? fundamentals.forward_pe ?? null,
    ps_ratio: raw?.ps_ratio ?? fundamentals.ps_ratio ?? null,
    peg_ratio: raw?.peg_ratio ?? fundamentals.peg_ratio ?? null,
    ev_ebitda: raw?.ev_ebitda ?? fundamentals.ev_ebitda ?? null,
    market_cap: raw?.market_cap ?? fundamentals.market_cap ?? null,
    beta: raw?.beta ?? fundamentals.beta ?? null,
    dividend_yield: raw?.dividend_yield ?? fundamentals.dividend_yield ?? null,
    revenue_ttm: raw?.revenue_ttm ?? fundamentals.revenue_ttm ?? null,
    eps_ttm: raw?.eps_ttm ?? fundamentals.eps_ttm ?? null,
    roe: raw?.roe ?? fundamentals.roe ?? null,
    roa: raw?.roa ?? fundamentals.roa ?? null,
    debt_equity: raw?.debt_equity ?? fundamentals.debt_equity ?? null,
    fcf_yield: raw?.fcf_yield ?? fundamentals.fcf_yield ?? null,
    current_ratio: raw?.current_ratio ?? fundamentals.current_ratio ?? null,
    analyst_target: raw?.analyst_target ?? analyst.target_avg ?? null,
    analyst_target_high: raw?.analyst_target_high ?? analyst.target_high ?? null,
    analyst_target_low: raw?.analyst_target_low ?? analyst.target_low ?? null,
    analyst_recommendation: raw?.analyst_recommendation ?? analyst.recommendation ?? null,
    number_of_analysts: raw?.number_of_analysts ?? analyst.analyst_count ?? null,
    rsi: raw?.rsi ?? technicals.rsi ?? null,
    trend: raw?.trend ?? technicals.trend ?? null,
    sma_50: raw?.sma_50 ?? technicals.sma_50 ?? null,
    sma_200: raw?.sma_200 ?? technicals.sma_200 ?? null,
    above_sma50: raw?.above_sma50 ?? technicals.above_sma50 ?? null,
    above_sma200: raw?.above_sma200 ?? technicals.above_sma200 ?? null,
    sma50_distance_pct: raw?.sma50_distance_pct ?? technicals.sma50_distance ?? null,
    sma200_distance_pct: raw?.sma200_distance_pct ?? technicals.sma200_distance ?? null,
    support: raw?.support ?? technicals.support ?? null,
    resistance: raw?.resistance ?? technicals.resistance ?? null,
    distance_52w_high_pct: raw?.distance_52w_high_pct ?? technicals.distance_52w_high ?? null,
    sma_20: raw?.sma_20 ?? technicals.sma_20 ?? null,
    atr_14: raw?.atr_14 ?? technicals.atr_14 ?? null,
    macd: raw?.macd ?? technicals.macd ?? null,
    macd_signal: raw?.macd_signal ?? technicals.macd_signal ?? null,
    macd_histogram: raw?.macd_histogram ?? technicals.macd_histogram ?? null,
    macd_bullish: raw?.macd_bullish ?? technicals.macd_bullish ?? null,
    obv_trend: raw?.obv_trend ?? technicals.obv_trend ?? null,
    rvol: raw?.rvol ?? technicals.rvol ?? null,
    float_shares: raw?.float_shares ?? technicals.float_shares ?? null,
    avg_volume: raw?.avg_volume ?? technicals.avg_volume ?? null,
    bid_ask_spread: raw?.bid_ask_spread ?? technicals.bid_ask_spread ?? null,
    iv_atm: raw?.iv_atm ?? expectedMove.iv ?? null,
    put_call_ratio: raw?.put_call_ratio ?? smartMoney.pcr_volume ?? null,
    expected_move_pct: raw?.expected_move_pct ?? expectedMove.pct ?? null,
    expected_move_usd: raw?.expected_move_usd ?? expectedMove.usd ?? null,
    max_pain: raw?.max_pain ?? smartMoney.max_pain ?? null,
    options_oi_url: raw?.options_oi_url ?? null,
    short_interest_pct: raw?.short_interest_pct ?? smartMoney.short_interest_pct ?? null,
    days_to_cover: raw?.days_to_cover ?? smartMoney.days_to_cover ?? null,
    squeeze_risk: raw?.squeeze_risk ?? smartMoney.squeeze_risk ?? null,
    insider_buys: raw?.insider_buys ?? smartMoney.insider_buys ?? 0,
    insider_sells: raw?.insider_sells ?? smartMoney.insider_sells ?? 0,
    insider_buy_value: raw?.insider_buy_value ?? smartMoney.insider_buy_value ?? 0,
    insider_sell_value: raw?.insider_sell_value ?? smartMoney.insider_sell_value ?? 0,
    insider_assessment: raw?.insider_assessment ?? smartMoney.insider_assessment ?? "normal",
    earnings_date: raw?.earnings_date ?? earnings.next_date ?? null,
    report_timing: raw?.report_timing ?? earnings.timing ?? null,
    earnings_countdown: raw?.earnings_countdown ?? earnings.countdown ?? null,
    earnings_today: raw?.earnings_today ?? earnings.is_today ?? false,
    eps_consensus: raw?.eps_consensus ?? earnings.eps_consensus ?? null,
    revenue_consensus: raw?.revenue_consensus ?? earnings.revenue_consensus ?? null,
    beats_of_8: raw?.beats_of_8 ?? earnings.beats_of_8 ?? null,
    avg_surprise_pct: raw?.avg_surprise_pct ?? earnings.avg_surprise_pct ?? null,
    last_surprise_pct: raw?.last_surprise_pct ?? earnings.last_surprise_pct ?? null,
    last_beat: raw?.last_beat ?? earnings.last_beat ?? null,
    quarterly_history: quarterlyHistory,
    news_bullets: newsBullets,
    finbert_sentiment: raw?.finbert_sentiment ?? sentiment.ticker_sentiment ?? null,
    sentiment_label: raw?.sentiment_label ?? sentiment.ticker_sentiment_label ?? null,
    sentiment_trend: raw?.sentiment_trend ?? null,
    sentiment_has_material: raw?.sentiment_has_material ?? Boolean(newsBullets.some((n: any) => n.is_material)),
    sentiment_count: raw?.sentiment_count ?? sentiment.ticker_article_count ?? newsBullets.length,
    sentiment_divergence: raw?.sentiment_divergence ?? sentiment.divergence ?? false,
    market_sentiment_avg: raw?.market_sentiment_avg ?? sentiment.market_avg_sentiment ?? null,
    sentiment_vs_market: raw?.sentiment_vs_market ?? null,
    market_sentiment_detail: raw?.market_sentiment_detail ?? null,
    reddit_sentiment: raw?.reddit_sentiment ?? redditSentiment,
    fear_greed: raw?.fear_greed ?? fearGreed,
    sector_earnings_upcoming: raw?.sector_earnings_upcoming ?? earnings.sector_calendar ?? [],
    is_watchlist: raw?.is_watchlist ?? false,
    web_prio: raw?.web_prio ?? raw?.watchlist_item?.web_prio ?? null,
    last_audit: raw?.last_audit ?? null,
    opportunity_score: raw?.opportunity_score ?? null,
    torpedo_score: raw?.torpedo_score ?? null,
    recommendation: raw?.recommendation ?? null,
    recommendation_label: raw?.recommendation_label ?? null,
    recommendation_reason: raw?.recommendation_reason ?? null,
    score_breakdown: raw?.score_breakdown ?? null,
    relative_strength: relativeStrength,
    company_profile: companyProfile,
    exchange: raw?.exchange ?? companyProfile.exchange ?? null,
    peers: fundamentals.peers ?? raw?.peers ?? [],
  } as ResearchData;
}

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

function ScoreBlock({ data, delta }: { data: ResearchData; delta?: ScoreDeltaData | null }) {
  const opp = data.opportunity_score;
  const torp = data.torpedo_score;
  const rec = data.recommendation;
  const label = data.recommendation_label;
  const reason = data.recommendation_reason;
  const [expanded, setExpanded] = useState(false);

  if (opp == null || torp == null) return null;

  // Ampel-Farben für Empfehlung
  const recColor =
    rec === "strong_buy" || rec === "buy_hedge"
      ? "text-[var(--accent-green)]"
      : rec === "strong_short" || rec === "potential_short"
      ? "text-[var(--accent-red)]"
      : rec === "watch"
      ? "text-[var(--accent-amber)]"
      : "text-[var(--text-secondary)]";

  const oppColor =
    opp >= 7 ? "text-[var(--accent-green)]"
    : opp >= 4 ? "text-[var(--accent-amber)]"
    : "text-[var(--accent-red)]";

  const torpColor =
    torp >= 7 ? "text-[var(--accent-red)]"
    : torp >= 4 ? "text-[var(--accent-amber)]"
    : "text-[var(--accent-green)]";

  // Delta-Funktionen
  const getDeltaDisplay = (current: number, historical: number | null) => {
    if (historical == null) return null;
    const diff = current - historical;
    if (Math.abs(diff) < 0.1) return null; // Keine Anzeige bei minimaler Änderung
    return {
      value: diff,
      arrow: diff > 0 ? <ChevronUp size={10} className="inline" /> : <ChevronDown size={10} className="inline" />,
      color: diff > 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"
    };
  };

  // Torpedo ist invertiert: steigender Wert = schlechter
  const getTorpedoDeltaDisplay = (current: number, historical: number | null) => {
    if (historical == null) return null;
    const diff = current - historical;
    if (Math.abs(diff) < 0.1) return null;
    return {
      value: diff,
      arrow: diff > 0 ? <ChevronUp size={10} className="inline" /> : <ChevronDown size={10} className="inline" />,
      color: diff > 0 ? "text-[var(--accent-red)]" : "text-[var(--accent-green)]"
    };
  };

  const oppYesterday = delta?.yesterday?.opportunity_score != null ? getDeltaDisplay(opp, delta.yesterday.opportunity_score) : null;
  const oppLastWeek = delta?.last_week?.opportunity_score != null ? getDeltaDisplay(opp, delta.last_week.opportunity_score) : null;
  const torpYesterday = delta?.yesterday?.torpedo_score != null ? getTorpedoDeltaDisplay(torp, delta.yesterday.torpedo_score) : null;
  const torpLastWeek = delta?.last_week?.torpedo_score != null ? getTorpedoDeltaDisplay(torp, delta.last_week.torpedo_score) : null;

  return (
    <div className={`rounded-xl border-2 p-5 ${
      rec === "strong_buy" || rec === "buy_hedge"
        ? "border-[var(--accent-green)]/40 bg-[var(--accent-green)]/5"
        : rec === "strong_short" || rec === "potential_short"
        ? "border-[var(--accent-red)]/40 bg-[var(--accent-red)]/5"
        : rec === "watch"
        ? "border-[var(--accent-amber)]/40 bg-[var(--accent-amber)]/5"
        : "border-[var(--border)] bg-[var(--bg-secondary)]"
    }`}>

      {/* Hauptzeile */}
      <div className="flex items-center justify-between flex-wrap gap-4">

        {/* Scores */}
        <div className="flex items-center gap-6">
          <div className="text-center">
            <p className="text-[10px] uppercase tracking-widest
                          text-[var(--text-muted)] mb-1">
              Opportunity
            </p>
            <p className={`text-4xl font-bold font-mono ${oppColor}`}>
              {opp.toFixed(1)}
            </p>
            <p className="text-[10px] text-[var(--text-muted)]">/ 10</p>
            {/* Delta-Anzeige */}
            <div className="mt-1 space-y-0.5">
              {oppYesterday && (
                <p className={`text-[9px] font-mono ${oppYesterday.color}`}>
                  {oppYesterday.arrow} {Math.abs(oppYesterday.value).toFixed(1)} vs gestern
                </p>
              )}
              {oppLastWeek && (
                <p className={`text-[9px] font-mono ${oppLastWeek.color}`}>
                  {oppLastWeek.arrow} {Math.abs(oppLastWeek.value).toFixed(1)} vs Woche
                </p>
              )}
            </div>
          </div>

          <div className="text-2xl font-light text-[var(--text-muted)]">
            vs
          </div>

          <div className="text-center">
            <p className="text-[10px] uppercase tracking-widest
                          text-[var(--text-muted)] mb-1">
              Torpedo
            </p>
            <p className={`text-4xl font-bold font-mono ${torpColor}`}>
              {torp.toFixed(1)}
            </p>
            <p className="text-[10px] text-[var(--text-muted)]">/ 10</p>
            {/* Delta-Anzeige */}
            <div className="mt-1 space-y-0.5">
              {torpYesterday && (
                <p className={`text-[9px] font-mono ${torpYesterday.color}`}>
                  {torpYesterday.arrow} {Math.abs(torpYesterday.value).toFixed(1)} vs gestern
                </p>
              )}
              {torpLastWeek && (
                <p className={`text-[9px] font-mono ${torpLastWeek.color}`}>
                  {torpLastWeek.arrow} {Math.abs(torpLastWeek.value).toFixed(1)} vs Woche
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Empfehlung */}
        <div className="flex-1 min-w-48">
          <p className={`text-2xl font-bold ${recColor}`}>
            {label || "—"}
          </p>
          {reason && (
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {reason}
            </p>
          )}
        </div>

        {/* Breakdown-Toggle */}
        {data.score_breakdown && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-[var(--accent-blue)]
                       hover:underline shrink-0"
          >
            {expanded ? "Details ausblenden ▲" : "Score-Details ▼"}
          </button>
        )}
      </div>

      {/* Score-Breakdown (aufklappbar) */}
      {expanded && data.score_breakdown && (
        <div className="mt-4 pt-4 border-t border-[var(--border)]
                        grid grid-cols-2 gap-4">

          <div>
            <p className="text-xs font-semibold text-[var(--accent-green)]
                          uppercase tracking-wider mb-2">
              Opportunity-Faktoren
            </p>
            <div className="space-y-1">
              {Object.entries(data.score_breakdown.opportunity ?? {}).map(
                ([key, val]) => (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-[var(--text-muted)]
                                     capitalize">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className={`font-mono font-semibold ${
                      (val as number) >= 7
                        ? "text-[var(--accent-green)]"
                        : (val as number) <= 3
                        ? "text-[var(--accent-red)]"
                        : "text-[var(--text-secondary)]"
                    }`}>
                      {(val as number).toFixed(1)}
                    </span>
                  </div>
                )
              )}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold text-[var(--accent-red)]
                          uppercase tracking-wider mb-2">
              Torpedo-Faktoren
            </p>
            <div className="space-y-1">
              {Object.entries(data.score_breakdown.torpedo ?? {}).map(
                ([key, val]) => (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-[var(--text-muted)]
                                     capitalize">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className={`font-mono font-semibold ${
                      (val as number) >= 7
                        ? "text-[var(--accent-red)]"
                        : (val as number) <= 3
                        ? "text-[var(--accent-green)]"
                        : "text-[var(--text-secondary)]"
                    }`}>
                      {(val as number).toFixed(1)}
                    </span>
                  </div>
                )
              )}
            </div>
          </div>

          <p className="col-span-2 text-[10px] text-[var(--text-muted)]
                        pt-2 border-t border-[var(--border)]">
            ⚠️ whisper_delta, guidance_trend, sector_regime sind
            aktuell noch nicht berechnet (Roadmap P1b).
          </p>
        </div>
      )}

      {/* Fear & Greed Badge */}
      {data.fear_greed?.score != null && (
        <div className="flex items-center gap-1.5 mt-2">
          <span className="text-[10px] text-[var(--text-muted)]">
            Markt:
          </span>
          <span className={`text-[10px] font-semibold ${
            (data.fear_greed.score ?? 50) <= 25
              ? "text-[var(--accent-red)]"
            : (data.fear_greed.score ?? 50) >= 75
              ? "text-[var(--accent-green)]"
            : "text-[var(--text-muted)]"
          }`}>
            {data.fear_greed.label}
            {" "}({Math.round(data.fear_greed.score ?? 50)})
          </span>
        </div>
      )}
    </div>
  );
}

// Trade Setup Block Component
function TradeSetupBlock({ 
  ticker, 
  data, 
  loading, 
  onLoad 
}: { 
  ticker: string; 
  data: ChartAnalysisData | null; 
  loading: boolean; 
  onLoad: () => void; 
}) {
  if (loading) {
    return (
      <div className="card p-4">
        <div className="flex items-center gap-2">
          <RefreshCw size={16} className="animate-spin text-[var(--accent-blue)]" />
          <span className="text-sm text-[var(--text-muted)]">
            Lade Chart-Analyse für {ticker}...
          </span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
              Trade Setup
            </p>
            <p className="text-sm text-[var(--text-secondary)]">
              Chart-Analyse nicht verfügbar
            </p>
          </div>
          <button
            onClick={onLoad}
            disabled={loading}
            className={`rounded-lg bg-[var(--accent-blue)] px-3 py-2 text-xs text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            Analyse laden
          </button>
        </div>
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="card p-4 border border-[var(--accent-red)]/40 bg-[var(--accent-red)]/5">
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} className="text-[var(--accent-red)]" />
          <span className="text-sm text-[var(--accent-red)]">
            Chart-Analyse fehlerhaft
          </span>
        </div>
      </div>
    );
  }

  const entryZone = data.entry_zone ?? {
    low: data.price,
    high: data.price,
  };
  const supportLevels = Array.isArray(data.support_levels)
    ? data.support_levels
    : [];
  const resistanceLevels = Array.isArray(data.resistance_levels)
    ? data.resistance_levels
    : [];
  const stopLossValue = data.stop_loss ?? null;
  const target1Value = data.target_1 ?? null;
  const target2Value = data.target_2 ?? null;

  const biasColor = 
    data.bias === "bullish" ? "text-[var(--accent-green)]"
    : data.bias === "bearish" ? "text-[var(--accent-red)]"
    : "text-[var(--text-secondary)]";

  const getStrengthColor = (strength: string) =>
    strength === "strong" ? "text-[var(--accent-green)]"
    : strength === "moderate" ? "text-[var(--accent-amber)]"
    : "text-[var(--text-secondary)]";

  return (
    <div className="card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
        Trade Setup - {data.ticker}
      </p>
      
      {/* Falling-Knife-Warnung */}
      {data.falling_knife_risk === "high" && (
        <div className="rounded-lg border border-[var(--accent-red)]/30
                        bg-[var(--accent-red)]/5 px-3 py-2 mb-3
                        flex items-start gap-2">
          <AlertTriangle size={13}
            className="text-[var(--accent-red)] shrink-0 mt-0.5" />
          <p className="text-xs text-[var(--accent-red)]">
            <span className="font-semibold">Falling-Knife-Risiko hoch</span>
            {data.floor_scenario
              ? ` — ${data.floor_scenario}` : ""}
          </p>
        </div>
      )}
      {data.falling_knife_risk === "medium" && (
        <div className="rounded-lg border border-amber-500/30
                        bg-amber-500/5 px-3 py-2 mb-3
                        flex items-start gap-2">
          <AlertTriangle size={13}
            className="text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-400">
            <span className="font-semibold">Vorsicht:</span>
            {" "}Trend prüfen vor Entry.
          </p>
        </div>
      )}
      
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Linke Seite: Levels */}
        <div className="space-y-3">
          {/* Entry Zone */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-3">
            <p className="text-xs font-semibold text-[var(--text-primary)] mb-2">Entry Zone</p>
            <p className="text-lg font-mono font-bold text-[var(--accent-blue)]">
              ${entryZone.low != null ? entryZone.low.toFixed(2) : "—"} - ${entryZone.high != null ? entryZone.high.toFixed(2) : "—"}
            </p>
          </div>

          {/* Stop Loss */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-3">
            <p className="text-xs font-semibold text-[var(--text-primary)] mb-2">Stop Loss</p>
            <p className="text-lg font-mono font-bold text-[var(--accent-red)]">
              ${stopLossValue != null ? stopLossValue.toFixed(2) : "—"}
            </p>
          </div>

          {/* Targets */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-3">
            <p className="text-xs font-semibold text-[var(--text-primary)] mb-2">Targets</p>
            <div className="space-y-1">
              <p className="text-sm font-mono text-[var(--accent-green)]">
                T1: ${target1Value != null ? target1Value.toFixed(2) : "—"}
              </p>
              <p className="text-sm font-mono text-[var(--accent-green)]">
                T2: ${target2Value != null ? target2Value.toFixed(2) : "—"}
              </p>
            </div>
          </div>
        </div>

        {/* Rechte Seite: Support/Resistance */}
        <div className="space-y-3">
          {/* Support Levels */}
          <div>
            <p className="text-xs font-semibold text-[var(--text-primary)] mb-2">Support</p>
            <div className="space-y-1">
              {supportLevels.map((level, idx) => (
                <div key={idx} className="flex justify-between items-center">
                  <span className="text-xs text-[var(--text-muted)]">{level.label}</span>
                  <span className={`text-sm font-mono ${getStrengthColor(level.strength)}`}>
                    ${level.price != null ? level.price.toFixed(2) : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Resistance Levels */}
          <div>
            <p className="text-xs font-semibold text-[var(--text-primary)] mb-2">Resistance</p>
            <div className="space-y-1">
              {resistanceLevels.map((level, idx) => (
                <div key={idx} className="flex justify-between items-center">
                  <span className="text-xs text-[var(--text-muted)]">{level.label}</span>
                  <span className={`text-sm font-mono ${getStrengthColor(level.strength)}`}>
                    ${level.price != null ? level.price.toFixed(2) : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Begründung — immer sichtbar wenn vorhanden */}
      {(data.why_entry || data.why_stop ||
        data.trend_context ||
        data.turnaround_conditions) && (
        <div className="mt-4 pt-3 border-t border-[var(--border)]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
            Begründung
          </p>
          <div className="space-y-3">
            {data.trend_context && (
              <div>
                <p className="text-[10px] font-semibold
                             text-[var(--text-muted)]
                             uppercase tracking-wider mb-1">
                  Trend-Kontext
                </p>
                <p className="text-xs
                              text-[var(--text-secondary)]
                              leading-relaxed">
                  {data.trend_context}
                </p>
              </div>
            )}

            {data.why_entry && (
              <div>
                <p className="text-[10px] font-semibold
                             text-[var(--accent-blue)]
                             uppercase tracking-wider mb-1">
                  Warum diese Entry-Zone?
                </p>
                <p className="text-xs
                              text-[var(--text-secondary)]
                              leading-relaxed">
                  {data.why_entry}
                </p>
              </div>
            )}

            {data.why_stop && (
              <div>
                <p className="text-[10px] font-semibold
                             text-[var(--accent-red)]
                             uppercase tracking-wider mb-1">
                  Warum dieser Stop?
                </p>
                <p className="text-xs
                              text-[var(--text-secondary)]
                              leading-relaxed">
                  {data.why_stop}
                </p>
              </div>
            )}

            {data.floor_scenario && (
              <div>
                <p className="text-[10px] font-semibold
                             text-[var(--text-muted)]
                             uppercase tracking-wider mb-1">
                  Wenn Stop reisst
                </p>
                <p className="text-xs
                              text-[var(--text-secondary)]
                              leading-relaxed">
                  {data.floor_scenario}
                </p>
              </div>
            )}

            {data.turnaround_conditions && (
              <div>
                <p className="text-[10px] font-semibold
                             text-[var(--accent-green)]
                             uppercase tracking-wider mb-1">
                  Turnaround-Bedingungen
                </p>
                <p className="text-xs
                              text-[var(--text-secondary)]
                              leading-relaxed">
                  {data.turnaround_conditions}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Analyse Text und Bias */}
      <div className="mt-4 pt-4 border-t border-[var(--border)]">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold uppercase tracking-wider mb-0">
            Bias: <span className={biasColor}>{data.bias.toUpperCase()}</span>
          </p>
          <div className="text-right">
            <p className="text-xs text-[var(--text-muted)]">
              RSI: {data.rsi?.toFixed(1) || "N/A"} | Trend: {data.trend}
            </p>
          </div>
        </div>
        
        {data.analysis_text && (
          <p className="text-sm text-[var(--text-secondary)] mb-2">
            {data.analysis_text}
          </p>
        )}

        {data.key_risk && (
          <div className="rounded-lg bg-[var(--accent-red)]/10 border border-[var(--accent-red)]/30 p-2">
            <p className="text-xs font-semibold text-[var(--accent-red)] mb-1">Key Risk</p>
            <p className="text-xs text-[var(--text-secondary)]">{data.key_risk}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Position Sizer Block Component
function PositionSizerBlock({
  currentPrice,
  accountSize,
  riskPercent,
  stopLoss,
  atr,
  target1,
  ivAtm,
  expectedMovePct,
  onAccountSizeChange,
  onRiskPercentChange,
  onStopLossChange,
}: {
  currentPrice: number;
  accountSize: number;
  riskPercent: number;
  stopLoss: number;
  atr?: number;
  target1?: number;
  ivAtm?: number;
  expectedMovePct?: number;
  onAccountSizeChange: (value: number) => void;
  onRiskPercentChange: (value: number) => void;
  onStopLossChange: (value: number) => void;
}) {
  // Berechnungen
  const riskAmount = (accountSize * riskPercent) / 100;
  const stopLossPercent = stopLoss;
  const stopLossPrice = currentPrice * (1 - stopLossPercent / 100);
  const stopLossDistance = currentPrice - stopLossPrice;
  const invalidStop = !Number.isFinite(stopLossDistance) || currentPrice <= 0 || stopLossDistance <= 0;
  const shares = !invalidStop ? Math.floor(riskAmount / stopLossDistance) : 0;
  const totalCost = shares * currentPrice;
  const maxLoss = !invalidStop ? shares * stopLossDistance : 0;

  // R:R — target1 aus ChartAnalysis wenn vorhanden, sonst 2:1 Fallback
  const upside = target1 && target1 > currentPrice
    ? target1 - currentPrice
    : stopLossDistance * 2;
  const rrRatio = stopLossDistance > 0
    ? (upside / stopLossDistance).toFixed(1)
    : "—";
  const rrLabel = target1 ? `Ziel $${target1.toFixed(2)}` : "2:1 Annahme";

  // Options-Sizing — nur wenn iv_atm vorhanden
  // Geschätzte ATM-Prämie: 0.4 × IV/100 × Kurs × √(21/252) ≈ Monats-Prämie
  const optionPremiumEst = (ivAtm && currentPrice)
    ? Math.round(currentPrice * (ivAtm / 100) * 0.4 * Math.sqrt(21 / 252) * 100) / 100
    : null;
  const contracts = (optionPremiumEst && riskAmount > 0)
    ? Math.floor(riskAmount / (optionPremiumEst * 100))
    : null;

  return (
    <div className="card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
        Position Sizer
      </p>
      
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Eingabefelder */}
        <div className="space-y-3">
          <div>
            <label className="text-xs text-[var(--text-muted)]">Kontogröße ($)</label>
            <input
              type="number"
              value={accountSize}
              onChange={(e) => onAccountSizeChange(parseFloat(e.target.value) || 0)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none"
            />
          </div>
          
          <div>
            <label className="text-xs text-[var(--text-muted)]">Risiko (%)</label>
            <input
              type="number"
              value={riskPercent}
              onChange={(e) => onRiskPercentChange(parseFloat(e.target.value) || 0)}
              step="0.1"
              min="0.1"
              max="10"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none"
            />
          </div>
          
          <div>
            <label className="text-xs text-[var(--text-muted)]">Stop Loss (%)</label>
            <input
              type="number"
              value={stopLoss}
              onChange={(e) => onStopLossChange(parseFloat(e.target.value) || 0)}
              step="0.1"
              min="0.5"
              max="20"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 text-sm font-mono text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none"
            />
            {atr && (
              <p className="text-[10px] text-[var(--text-muted)] mt-1">
                ATR(14): ${atr.toFixed(2)} = {((atr / currentPrice) * 100).toFixed(1)}%
              </p>
            )}
          </div>
        </div>

        {/* Berechnungen */}
        <div className="space-y-3">
          {invalidStop && (
            <div className="rounded-lg border border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
              Stop-Loss / Einstieg ist ungültig — bitte Kursdaten prüfen.
            </div>
          )}

          <StatCell 
            label="Risiko-Betrag" 
            value={`$${maxLoss.toFixed(2)}`}
            sub={`${riskPercent}% von $${accountSize.toLocaleString()}`}
          />
          
          <StatCell 
            label="Aktienanzahl" 
            value={shares.toLocaleString()}
            sub={`Kapitaleinsatz $${totalCost.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          />
          
          <StatCell 
            label="Max Verlust" 
            value={`$${maxLoss.toFixed(2)}`}
            sub={`Stop @ $${stopLossPrice.toFixed(2)}`}
          />
          
          <StatCell 
            label="R:R Verhältnis" 
            value={`1:${rrRatio}`}
            sub={rrLabel}
          />
        </div>
      </div>

      {/* Options-Sizing — nur wenn contracts !== null */}
      {contracts !== null && (
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
            Options-Sizing
          </p>
          <StatCell
            label="Kontrakte (ATM)"
            value={contracts.toString()}
            sub={`Prämie ~$${optionPremiumEst?.toFixed(2)} × 100`}
          />
          {expectedMovePct && (
            <p className="text-[10px] text-[var(--text-muted)] mt-1">
              Expected Move ±{expectedMovePct.toFixed(1)}%
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function TickerChatBlock({
  ticker,
  contextSnapshot,
}: {
  ticker: string;
  contextSnapshot: Record<string, unknown>;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const next: ChatMsg[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setLoading(true);

    try {
      const res = await fetch(`/api/analysis/chat/${ticker}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: next,
          context_snapshot: contextSnapshot,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Fehler — Antwort konnte nicht geladen werden." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const suggestions = [
    "Was ändert sich wenn VIX auf 35 steigt?",
    "Welches Options-Setup passt zur aktuellen Empfehlung?",
    "Was sind die größten Torpedorisiken?",
  ];

  return (
    <div className="card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
        AI Analyst — {ticker}
      </p>

      {/* Nachrichten-Verlauf */}
      {messages.length === 0 ? (
        <div className="space-y-2 mb-3">
          <p className="text-xs text-[var(--text-secondary)]">
            Stelle eine Frage zum aktuellen Setup:
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => { setInput(s); }}
                className="rounded-lg border border-[var(--border)] px-3 py-1.5
                           text-xs text-[var(--text-secondary)]
                           hover:border-[var(--accent-blue)]
                           hover:text-[var(--accent-blue)] transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-3 mb-3 max-h-72 overflow-y-auto pr-1">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`rounded-xl px-3 py-2 text-xs leading-relaxed max-w-[85%]
                  ${msg.role === "user"
                    ? "bg-[var(--accent-blue)] text-white"
                    : "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
                  }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-xl px-3 py-2 bg-[var(--bg-tertiary)]">
                <RefreshCw size={12} className="animate-spin text-[var(--text-muted)]" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Frage zum Setup..."
          disabled={loading}
          className="flex-1 rounded-lg border border-[var(--border)]
                     bg-[var(--bg-secondary)] px-3 py-2 text-sm
                     text-[var(--text-primary)] placeholder-[var(--text-muted)]
                     focus:border-[var(--accent-blue)] outline-none
                     disabled:opacity-50"
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm
                     text-white hover:opacity-90 disabled:opacity-40
                     disabled:cursor-not-allowed transition-opacity"
        >
          Senden
        </button>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            disabled={loading}
            className="rounded-lg border border-[var(--border)] px-3 py-2
                       text-xs text-[var(--text-muted)]
                       hover:text-[var(--text-primary)] transition-colors"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}

function PeerComparisonBlock({
  mainTicker,
  data,
  loading,
}: {
  mainTicker: string;
  data: PeerComparisonData | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="card p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
          Peer-Vergleich
        </p>
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <RefreshCw size={12} className="animate-spin" />
          Lade Peer-Daten…
        </div>
      </div>
    );
  }

  const peers = data?.peers ?? [];
  if (!data || peers.length <= 1) return null;

  const cols: { key: keyof PeerItem; label: string; fmt: (v: unknown) => string }[] = [
    { key: "price",        label: "Kurs",   fmt: v => v != null ? `$${(v as number).toFixed(2)}` : "—" },
    { key: "change_5d_pct",label: "5T%",    fmt: v => v != null ? `${(v as number) >= 0 ? "+" : ""}${(v as number).toFixed(1)}%` : "—" },
    { key: "pe_ratio",     label: "P/E",    fmt: v => v != null ? (v as number).toFixed(1) : "—" },
    { key: "ps_ratio",     label: "P/S",    fmt: v => v != null ? (v as number).toFixed(1) : "—" },
    { key: "market_cap_b", label: "MCap B", fmt: v => v != null ? `$${(v as number).toFixed(0)}B` : "—" },
    { key: "rvol",         label: "RVOL",   fmt: v => v != null ? `${(v as number).toFixed(1)}×` : "—" },
  ];

  return (
    <div className="card p-4 overflow-x-auto">
      <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
        Peer-Vergleich
      </p>
      <table className="w-full text-xs min-w-[420px]">
        <thead>
          <tr>
            <th className="text-left pb-2 text-[var(--text-muted)] font-medium w-24">Ticker</th>
            {cols.map(c => (
              <th key={c.key} className="text-right pb-2 text-[var(--text-muted)] font-medium px-2">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {peers.map((peer, i) => {
            const isMain = peer.ticker === mainTicker;
            return (
              <tr
                key={peer.ticker}
                className={`border-t border-[var(--border)] ${
                  isMain ? "bg-[var(--accent-blue)]/5" : i % 2 === 0 ? "" : "bg-[var(--bg-tertiary)]/40"
                }`}
              >
                <td className="py-2 pr-2">
                  <span className={`font-mono font-semibold ${isMain ? "text-[var(--accent-blue)]" : "text-[var(--text-primary)]"}`}>
                    {peer.ticker}
                  </span>
                  {isMain && (
                    <span className="ml-1 text-[9px] text-[var(--accent-blue)]">▶</span>
                  )}
                  <br />
                  <span className="text-[var(--text-muted)] text-[10px] truncate block max-w-[88px]">
                    {peer.name}
                  </span>
                </td>
                {cols.map(c => {
                  const raw = peer[c.key];
                  const str = c.fmt(raw);
                  const isChange = c.key === "change_5d_pct";
                  const color = isChange && raw != null
                    ? (raw as number) >= 0
                      ? "text-[var(--accent-green)]"
                      : "text-[var(--accent-red)]"
                    : "text-[var(--text-primary)]";
                  return (
                    <td key={c.key} className={`py-2 px-2 text-right font-mono ${color}`}>
                      {str}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SentimentBlock({ data }: { data: ResearchData }) {
  const ticker_s = data.finbert_sentiment;
  const market_s = data.market_sentiment_avg;
  const vs       = data.sentiment_vs_market;
  const count    = data.sentiment_count ?? 0;

  if (ticker_s == null || count === 0) return null;

  const sentColor = (v: number) =>
    v >  0.15 ? "text-[var(--accent-green)]"
    : v < -0.15 ? "text-[var(--accent-red)]"
    : "text-[var(--text-muted)]";

  const sentLabel = (v: number) =>
    v >  0.3 ? "Stark bullish"
    : v >  0.15 ? "Bullish"
    : v < -0.3 ? "Stark bearish"
    : v < -0.15 ? "Bearish"
    : "Neutral";

  const trendIcon =
    data.sentiment_trend === "improving"     ? "↑" :
    data.sentiment_trend === "deteriorating" ? "↓" : "→";

  const trendColor =
    data.sentiment_trend === "improving"     ?
      "text-[var(--accent-green)]" :
    data.sentiment_trend === "deteriorating" ?
      "text-[var(--accent-red)]" :
    "text-[var(--text-muted)]";

  return (
    <div className="card p-4">
      <p className="text-[10px] font-semibold uppercase
                    tracking-[0.25em] text-[var(--text-muted)] mb-3">
        News-Sentiment ({count} Artikel)
      </p>

      <div className="grid grid-cols-3 gap-3 mb-3">

        {/* Ticker Sentiment */}
        <div className="rounded-lg bg-[var(--bg-tertiary)] p-3
                        text-center">
          <p className="text-[10px] text-[var(--text-muted)] mb-1">
            {data.ticker}
          </p>
          <p className={`text-xl font-bold font-mono
                         ${sentColor(ticker_s)}`}>
            {ticker_s >= 0 ? "+" : ""}
            {ticker_s.toFixed(2)}
          </p>
          <p className={`text-[10px] mt-1 ${sentColor(ticker_s)}`}>
            {sentLabel(ticker_s)}
          </p>
          <p className={`text-[10px] mt-0.5 ${trendColor}`}>
            {trendIcon} {data.sentiment_trend}
          </p>
        </div>

        {/* S&P 500 Markt-Sentiment */}
        {market_s != null && (
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-3
                          text-center">
            <p className="text-[10px] text-[var(--text-muted)] mb-1">
              S&P 500 (Markt)
            </p>
            <p className={`text-xl font-bold font-mono
                           ${sentColor(market_s)}`}>
              {market_s >= 0 ? "+" : ""}
              {market_s.toFixed(2)}
            </p>
            <p className={`text-[10px] mt-1
                           ${sentColor(market_s)}`}>
              {sentLabel(market_s)}
            </p>
          </div>
        )}

        {/* Delta: Ticker vs. Markt */}
        {vs != null && (
          <div className={`rounded-lg p-3 text-center ${
            vs >  0.1
              ? "bg-[var(--accent-green)]/10"
            : vs < -0.1
              ? "bg-[var(--accent-red)]/10"
            : "bg-[var(--bg-tertiary)]"
          }`}>
            <p className="text-[10px] text-[var(--text-muted)]
                           mb-1">
              vs. Markt
            </p>
            <p className={`text-xl font-bold font-mono ${
              vs >  0.1 ? "text-[var(--accent-green)]"
              : vs < -0.1 ? "text-[var(--accent-red)]"
              : "text-[var(--text-muted)]"
            }`}>
              {vs >= 0 ? "+" : ""}{vs.toFixed(2)}
            </p>
            <p className={`text-[10px] mt-1 ${
              vs >  0.1 ? "text-[var(--accent-green)]"
              : vs < -0.1 ? "text-[var(--accent-red)]"
              : "text-[var(--text-muted)]"
            }`}>
              {vs >  0.1 ? "Stärker als Markt"
             : vs < -0.1 ? "Schwächer als Markt"
             : "Markt-neutral"}
            </p>
          </div>
        )}
        {/* Reddit Sentiment */}
        {data.reddit_sentiment?.mentions
         && data.reddit_sentiment.mentions > 0 && (
          <div className="rounded-lg
                           bg-[var(--bg-tertiary)] p-3">
            <p className="text-[10px]
                           text-[var(--text-muted)] mb-1">
              Reddit (WSB/stocks)
            </p>
            <p className={`text-lg font-bold font-mono ${
              (data.reddit_sentiment.score ?? 0) > 0.1
                ? "text-[var(--accent-green)]"
              : (data.reddit_sentiment.score ?? 0) < -0.1
                ? "text-[var(--accent-red)]"
              : "text-amber-400"
            }`}>
              {data.reddit_sentiment.label ?? "—"}
            </p>
            <p className="text-[10px]
                           text-[var(--text-muted)] mt-1">
              {data.reddit_sentiment.mentions} Erwähnungen (24h)
            </p>
            {/* Divergenz-Warnung */}
            {data.reddit_sentiment.score !== null
             && (data.reddit_sentiment.score ?? 0) > 0.15
             && data.insider_assessment === "bearish" && (
              <p className="text-[10px]
                             text-[var(--accent-red)] mt-1
                             font-semibold">
                ⚠ Retail gierig + Insider bearish
              </p>
            )}
          </div>
        )}
      </div>

      {/* Markt-Kontext Detail — aufklappbar */}
      {data.market_sentiment_detail
       && Object.keys(data.market_sentiment_detail).length > 0
       && (
        <div className="pt-3 border-t border-[var(--border)]">
          <p className="text-[10px]
                         text-[var(--text-muted)]
                         uppercase tracking-wider mb-2">
            Markt-Kontext (FinBERT)
          </p>
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-4">
            {Object.entries(data.market_sentiment_detail)
              .map(([cat, s]: [string, any]) => (
              <div key={cat}
                   className="rounded bg-[var(--bg-tertiary)]
                              px-2 py-1.5 text-center">
                <p className="text-[9px] text-[var(--text-muted)]
                               capitalize mb-0.5">
                  {cat.replace("_", " ")}
                </p>
                <p className={`text-xs font-mono font-semibold
                               ${sentColor(s.score)}`}>
                  {s.score >= 0 ? "+" : ""}
                  {s.score.toFixed(2)}
                </p>
                <p className="text-[9px] text-[var(--text-muted)]">
                  {s.count} Art.
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnungen */}
      {data.sentiment_divergence && (
        <div className="mt-3 flex items-start gap-2 rounded-lg
                        bg-[var(--accent-red)]/5
                        border border-[var(--accent-red)]/20
                        px-3 py-2">
          <AlertTriangle size={12}
            className="text-[var(--accent-red)] shrink-0 mt-0.5" />
          <p className="text-xs text-[var(--accent-red)]">
            Sentiment-Divergenz — historisch positiv,
            aber aktueller Trend dreht bearish.
            Mögliches Buy-the-Rumor-Muster.
          </p>
        </div>
      )}

      {data.sentiment_has_material && (
        <div className="mt-2 flex items-start gap-2 rounded-lg
                        bg-amber-500/5
                        border border-amber-500/20
                        px-3 py-2">
          <AlertTriangle size={12}
            className="text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-400">
            Material Event in den letzten News erkannt
            — Ad-Hoc Meldung die den Kurs bewegen kann.
          </p>
        </div>
      )}
    </div>
  );
}

function RelativeStrengthBlock({ data }: { data: ResearchData }) {
  const rs = data.relative_strength;
  if (!rs) return null;

  const fmtRel = (val: number | null | undefined) => {
    if (val == null) return "—";
    const sign = val > 0 ? "+" : "";
    return `${sign}${val.toFixed(1)}%`;
  };

  const relColor = (val: number | null | undefined) => {
    if (val == null) return "text-[var(--text-muted)]";
    if (val > 0.5) return "text-[var(--accent-green)]";
    if (val < -0.5) return "text-[var(--accent-red)]";
    return "text-[var(--text-muted)]";
  };

  const signalColor =
    rs.signal === "bullish" ? "text-[var(--accent-green)]"
    : rs.signal === "bearish" ? "text-[var(--accent-red)]"
    : "text-amber-400";

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">
          Relative Stärke
        </p>
        <span className={`text-xs font-semibold ${signalColor}`}>
          {rs.label}
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">

        {/* vs. S&P 500 */}
        <div className="rounded-lg bg-[var(--bg-tertiary)] p-3">
          <p className="text-[10px] text-[var(--text-muted)] mb-2">
            vs. S&P 500 (SPY)
          </p>
          <div className="space-y-1.5">
            {[
              { label: "Heute", ticker: data.change_pct, bench: rs.spy_1d, rel: rs.vs_spy_1d },
              { label: "5 Tage", ticker: data.price_change_5d, bench: rs.spy_5d, rel: rs.vs_spy_5d },
              { label: "20 Tage", ticker: data.price_change_30d, bench: rs.spy_1m, rel: rs.vs_spy_1m },
            ].map(row => (
              <div key={row.label}
                   className="flex items-center justify-between">
                <span className="text-[10px] text-[var(--text-muted)]
                                  w-12">{row.label}</span>
                <span className="text-[10px] font-mono
                                  text-[var(--text-secondary)]">
                  {row.ticker != null
                    ? `${row.ticker >= 0 ? "+" : ""}${row.ticker.toFixed(1)}%` 
                    : "—"}
                  {" "}vs{" "}
                  {row.bench != null
                    ? `${row.bench >= 0 ? "+" : ""}${row.bench.toFixed(1)}%` 
                    : "—"}
                </span>
                <span className={`text-xs font-semibold font-mono
                                   w-14 text-right ${relColor(row.rel)}`}>
                  {fmtRel(row.rel)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* vs. Sektor */}
        <div className="rounded-lg bg-[var(--bg-tertiary)] p-3">
          <p className="text-[10px] text-[var(--text-muted)] mb-2">
            vs. Sektor
            {rs.sector_etf && (
              <span className="ml-1 text-[var(--accent-blue)]">
                {rs.sector_etf} · {data.sector}
              </span>
            )}
          </p>
          {rs.sector_etf ? (
            <div className="space-y-1.5">
              {[
                { label: "Heute", ticker: data.change_pct, bench: rs.sector_1d, rel: rs.vs_sector_1d },
                { label: "5 Tage", ticker: data.price_change_5d, bench: rs.sector_5d, rel: rs.vs_sector_5d },
                { label: "20 Tage", ticker: data.price_change_30d, bench: rs.sector_1m, rel: rs.vs_sector_1m },
              ].map(row => (
                <div key={row.label}
                     className="flex items-center justify-between">
                  <span className="text-[10px] text-[var(--text-muted)]
                                    w-12">{row.label}</span>
                  <span className="text-[10px] font-mono
                                    text-[var(--text-secondary)]">
                    {row.ticker != null
                      ? `${row.ticker >= 0 ? "+" : ""}${row.ticker.toFixed(1)}%` 
                      : "—"}
                    {" "}vs{" "}
                    {row.bench != null
                      ? `${row.bench >= 0 ? "+" : ""}${row.bench.toFixed(1)}%` 
                      : "—"}
                  </span>
                  <span className={`text-xs font-semibold font-mono
                                     w-14 text-right ${relColor(row.rel)}`}>
                    {fmtRel(row.rel)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">
              Sektor nicht erkannt — kein ETF-Mapping verfügbar.
            </p>
          )}
        </div>
      </div>

      <p className="text-[10px] text-[var(--text-muted)] mt-3">
        Positiver Wert = Titel outperformt den Benchmark.
        Titelspezifische Bewegung vs. Markt-Rauschen.
      </p>
    </div>
  );
}

// Earnings Context Banner Component
function EarningsContextBanner({ data }: { data: ResearchData }) {
  const countdown = data.earnings_countdown;
  if (countdown == null || countdown > 30) return null;

  const price = data.price;
  const move = data.expected_move_pct;
  const moveUsd = data.expected_move_usd;
  const change30d = data.price_change_30d;

  const breakEvenUp = price && moveUsd
    ? (price + moveUsd).toFixed(2) : null;
  const breakEvenDown = price && moveUsd
    ? (price - moveUsd).toFixed(2) : null;

  // Buy-the-Rumor: Kurs stark gestiegen VOR Earnings
  const buyRumorRisk =
    change30d != null && change30d > 10 && countdown <= 14;

  return (
    <div className={`rounded-xl p-4 border-2 ${
      countdown <= 3
        ? "border-[var(--accent-red)]/50 bg-[var(--accent-red)]/5"
        : countdown <= 7
        ? "border-amber-500/50 bg-amber-500/5"
        : "border-[var(--border)] bg-[var(--bg-secondary)]"
    }`}>

      {/* Hauptzeile */}
      <div className="flex items-start justify-between
                      flex-wrap gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-lg font-bold ${
              countdown <= 3 ? "text-[var(--accent-red)]"
              : countdown <= 7 ? "text-amber-400"
              : "text-[var(--text-primary)]"
            }`}>
              {data.earnings_today
                ? "Earnings HEUTE"
                : `Earnings in ${countdown} Tagen`}
            </span>
            {data.report_timing && (
              <span className="text-xs text-[var(--text-muted)]
                               bg-[var(--bg-tertiary)] px-2 py-0.5 rounded">
                {data.report_timing === "before_market"
                  ? "Pre-Market"
                  : data.report_timing === "after_market"
                  ? "After-Market"
                  : data.report_timing}
              </span>
            )}
          </div>
          {data.earnings_date && (
            <p className="text-xs text-[var(--text-muted)]">
              {(() => {
                try {
                  const d = new Date(data.earnings_date!);
                  if (Number.isNaN(d.getTime())) return data.earnings_date || "—";
                  return d.toLocaleDateString("de-DE", {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  });
                } catch {
                  return "—";
                }
              })()}
            </p>
          )}
        </div>

        {/* Expected Move */}
        {move != null && (
          <div className="text-right">
            <p className="text-[10px] text-[var(--text-muted)]">
              Expected Move (Options)
            </p>
            <p className="text-xl font-bold font-mono">
              ±{move.toFixed(1)}%
            </p>
            {moveUsd && (
              <p className="text-xs text-[var(--text-muted)]">
                ±${moveUsd.toFixed(2)} pro Aktie
              </p>
            )}
          </div>
        )}
      </div>

      {/* Break-Even Level */}
      {breakEvenUp && breakEvenDown && (
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-2 text-center">
            <p className="text-[10px] text-[var(--accent-red)]">
              Break-Even unten
            </p>
            <p className="text-sm font-bold font-mono
                           text-[var(--accent-red)]">
              ${breakEvenDown}
            </p>
            <p className="text-[10px] text-[var(--text-muted)]">
              Kurs muss drüber bleiben
            </p>
          </div>
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-2
                           text-center">
            <p className="text-[10px] text-[var(--text-muted)]">
              Aktueller Kurs
            </p>
            <p className="text-sm font-bold font-mono
                           text-[var(--text-primary)]">
              ${price?.toFixed(2) || "—"}
            </p>
            <p className="text-[10px] text-[var(--text-muted)]">
              heute
            </p>
          </div>
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-2
                           text-center">
            <p className="text-[10px] text-[var(--accent-green)]">
              Break-Even oben
            </p>
            <p className="text-sm font-bold font-mono
                           text-[var(--accent-green)]">
              ${breakEvenUp}
            </p>
            <p className="text-[10px] text-[var(--text-muted)]">
              Kurs muss drüber steigen
            </p>
          </div>
        </div>
      )}

      {/* Buy-the-Rumor Warnung */}
      {buyRumorRisk && (
        <div className="flex items-start gap-2 rounded-lg
                         bg-[var(--accent-red)]/10
                         border border-[var(--accent-red)]/20
                         px-3 py-2 mt-2">
          <AlertTriangle size={12}
            className="text-[var(--accent-red)] shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold
                           text-[var(--accent-red)]">
              Buy-the-Rumor Risiko — Kurs +{change30d?.toFixed(1)}%
              in 30 Tagen vor Earnings
            </p>
            <p className="text-[10px] text-[var(--accent-red)]/80 mt-0.5">
              Viel ist bereits eingepreist. Ein Beat kann trotzdem
              zu Abverkauf führen wenn die Erwartungen zu hoch sind.
              Enger Stop empfohlen.
            </p>
          </div>
        </div>
      )}

      {/* Konsens */}
      {(data.eps_consensus || data.revenue_consensus) && (
        <div className="flex gap-4 mt-3 pt-3
                         border-t border-[var(--border)]">
          {data.eps_consensus && (
            <div>
              <p className="text-[10px] text-[var(--text-muted)]">
                EPS Konsens
              </p>
              <p className="text-sm font-mono font-semibold
                             text-[var(--text-primary)]">
                ${data.eps_consensus.toFixed(2)}
              </p>
            </div>
          )}
          {data.revenue_consensus && (
            <div>
              <p className="text-[10px] text-[var(--text-muted)]">
                Revenue Konsens
              </p>
              <p className="text-sm font-mono font-semibold
                             text-[var(--text-primary)]">
                {data.revenue_consensus >= 1e9
                  ? `$${(data.revenue_consensus / 1e9).toFixed(1)}B` 
                  : `$${(data.revenue_consensus / 1e6).toFixed(0)}M`}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Watchlist-Earnings nächste 14T */}
      {data.sector_earnings_upcoming
       && data.sector_earnings_upcoming.length > 0 && (
        <div className="mt-3 pt-3 border-t
                         border-[var(--border)]">
          <p className="text-[10px]
                         text-[var(--text-muted)]
                         uppercase tracking-wider mb-2">
            Watchlist-Earnings nächste 14T
          </p>
          <div className="flex flex-wrap gap-2">
            {data.sector_earnings_upcoming.map(e => (
              <a
                key={e.ticker}
                href={`/research/${e.ticker}`}
                className="flex items-center gap-1.5
                            rounded-lg px-2.5 py-1.5
                            bg-[var(--bg-tertiary)]
                            hover:bg-[var(--bg-elevated)]
                            text-xs transition-colors"
              >
                <span className="font-mono font-semibold
                                  text-[var(--accent-blue)]">
                  {e.ticker}
                </span>
                {e.date && (
                  <span className="text-[var(--text-muted)]">
                    {new Date(e.date)
                      .toLocaleDateString("de-DE", {
                        day: "numeric",
                        month: "short",
                      })}
                  </span>
                )}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Company Profile Block (P1c) ────────────────────────────────
function CompanyProfileBlock({
  profile,
  ticker,
}: {
  profile: ResearchData["company_profile"];
  ticker: string;
}) {
  if (!profile) return null;
  if (
    !profile.ceo && !profile.description
    && !profile.employees
  ) return null;

  return (
    <div className="card p-5">
      <h3 className="text-xs font-semibold uppercase
                     tracking-widest text-[var(--text-muted)]
                     mb-4">
        Unternehmen
      </h3>
      <div className="space-y-3">

        {/* CEO + Employees */}
        <div className="flex items-center
                        justify-between flex-wrap gap-2">
          {profile.ceo && (
            <div>
              <p className="text-[10px] text-[var(--text-muted)]">
                CEO
              </p>
              <p className="text-sm font-medium
                             text-[var(--text-primary)]">
                {profile.ceo}
              </p>
            </div>
          )}
          {profile.employees && (
            <div className="text-right">
              <p className="text-[10px] text-[var(--text-muted)]">
                Mitarbeiter
              </p>
              <p className="text-sm font-mono
                             text-[var(--text-primary)]">
                {profile.employees.toLocaleString("de-DE")}
              </p>
            </div>
          )}
        </div>

        {/* Meta: IPO, Country, Exchange */}
        {(profile.ipo_date || profile.country
          || profile.exchange) && (
          <div className="flex flex-wrap gap-3
                          text-xs text-[var(--text-muted)]">
            {profile.country && (
              <span>🌍 {profile.country}</span>
            )}
            {profile.exchange && (
              <span>📊 {profile.exchange}</span>
            )}
            {profile.ipo_date && (
              <span>
                IPO: {new Date(profile.ipo_date)
                  .getFullYear()}
              </span>
            )}
            {profile.website && (
              <a
                href={profile.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--accent-blue)]
                           hover:underline"
              >
                Website ↗
              </a>
            )}
          </div>
        )}

        {/* Beschreibung */}
        {profile.description && (
          <p className="text-xs text-[var(--text-secondary)]
                         leading-relaxed border-t
                         border-[var(--border)] pt-3">
            {profile.description}
          </p>
        )}

        {/* Peers */}
        {profile.peers && profile.peers.length > 0 && (
          <div className="border-t border-[var(--border)] pt-3">
            <p className="text-[10px] text-[var(--text-muted)]
                           mb-2">
              Peers
            </p>
            <div className="flex flex-wrap gap-1.5">
              {profile.peers.map((peer) => (
                <a
                  key={peer}
                  href={`/research/${peer}`}
                  className="rounded px-2 py-1 text-xs
                             font-mono font-semibold
                             bg-[var(--bg-tertiary)]
                             text-[var(--accent-blue)]
                             hover:bg-[var(--bg-elevated)]
                             transition-colors"
                >
                  {peer}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Options OI Block Component
function OptionsOiBlock({
  data,
  currentPrice,
  onLoad,
  loading,
}: {
  data: OptionsOiData | null;
  currentPrice?: number | null;
  onLoad: () => void;
  loading: boolean;
}) {
  // Zeige Button wenn noch nicht geladen
  if (!data && !loading) {
    return (
      <div className="card p-4 text-center">
        <p className="text-xs text-[var(--text-muted)] mb-3">
          Options Open Interest & Max Pain
        </p>
        <button
          onClick={onLoad}
          className="text-xs rounded-lg
                     border border-[var(--border)]
                     px-4 py-2
                     text-[var(--accent-blue)]
                     hover:bg-[var(--bg-tertiary)]
                     transition-colors"
        >
          ⚡ OI-Heatmap laden
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card p-4 text-center">
        <p className="text-xs text-[var(--text-muted)]
                        animate-pulse">
          Lade Optionskette…
        </p>
      </div>
    );
  }

  if (!data || data.expirations?.length === 0) {
    return null;
  }

  // Erste gültige Expiration
  const exp = data.expirations.find(
    e => !e.error && e.top_oi_strikes?.length > 0
  );
  if (!exp) return null;

  // Max OI für Balken-Normalisierung
  const maxOi = Math.max(
    ...exp.top_oi_strikes.map(s => s.total_oi), 1
  );

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)]">
          Options OI — {exp.expiry}
        </h3>
        <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)]">
          {exp.pcr_oi != null && (
            <span>
              PCR-OI:{" "}
              <span className={
                exp.pcr_oi > 1.2
                  ? "text-[var(--accent-red)]"
                : exp.pcr_oi < 0.8
                  ? "text-[var(--accent-green)]"
                : "text-amber-400"
              }>
                {exp.pcr_oi.toFixed(2)}
              </span>
            </span>
          )}
          <span className="text-[var(--accent-blue)] font-semibold">
            Max Pain: ${exp.max_pain.toFixed(0)}
          </span>
        </div>
      </div>

      {/* Strike-Heatmap */}
      <div className="space-y-1.5">
        {exp.top_oi_strikes
          .sort((a, b) => b.strike - a.strike)
          .map((s) => {
            const isMaxPain =
              Math.abs(s.strike - exp.max_pain) < 1;
            const isAtm = currentPrice
              && Math.abs(s.strike - currentPrice)
                 / currentPrice < 0.02;
            const callPct = s.total_oi > 0
              ? s.call_oi / maxOi
              : 0;
            const putPct = s.total_oi > 0
              ? s.put_oi / maxOi
              : 0;

            return (
              <div
                key={s.strike}
                className={`rounded-lg px-3 py-1.5 ${
                  isMaxPain
                    ? "border border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/5"
                  : isAtm
                    ? "border border-[var(--border)] bg-[var(--bg-tertiary)]"
                  : ""
                }`}
              >
                {/* Strike-Label */}
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-mono
                                    font-semibold ${
                    isMaxPain
                      ? "text-[var(--accent-blue)]"
                    : isAtm
                      ? "text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)]"
                  }`}>
                    ${s.strike.toFixed(0)}
                    {isMaxPain && " ← Max Pain"}
                    {isAtm && !isMaxPain && " ← ATM"}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {(s.total_oi / 1000).toFixed(0)}K OI
                  </span>
                </div>
                {/* Call/Put Balken */}
                <div className="flex gap-1 h-1.5">
                  {/* Calls (grün, links) */}
                  <div className="flex-1 flex justify-end">
                    <div
                      className="h-full rounded-l-full
                                  bg-[var(--accent-green)]
                                  opacity-70"
                      style={{ width: `${callPct * 100}%` }}
                    />
                  </div>
                  {/* Puts (rot, rechts) */}
                  <div className="flex-1">
                    <div
                      className="h-full rounded-r-full
                                  bg-[var(--accent-red)]
                                  opacity-70"
                      style={{ width: `${putPct * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
      </div>

      <div className="flex justify-between mt-3
                       text-[10px]
                       text-[var(--text-muted)]">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full
                           bg-[var(--accent-green)]
                           inline-block" />
          Calls: {(exp.total_call_oi / 1000).toFixed(0)}K
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full
                           bg-[var(--accent-red)]
                           inline-block" />
          Puts: {(exp.total_put_oi / 1000).toFixed(0)}K
        </span>
      </div>
    </div>
  );
}

// ── 10-Q Filing Diff Block ───────────────────────────────────────
function FilingDiffBlock({
  data,
  loading,
  onLoad,
}: {
  data: FilingDiffData | null;
  loading: boolean;
  onLoad: () => void;
}) {
  if (!data && !loading) {
    return (
      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              10-Q Tonalitäts-Analyse
            </h3>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
              Vergleicht Management-Sprache
              zwischen zwei Quartalsberichten
            </p>
          </div>
          <button
            onClick={onLoad}
            className="text-xs rounded-lg
                        bg-[var(--accent-blue)]
                        text-white px-4 py-2
                        hover:opacity-90"
          >
            ⚡ 10-Q analysieren
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card p-5">
        <p className="text-xs text-[var(--text-muted)]
                        animate-pulse">
          Lade 10-Q Berichte von SEC EDGAR
          und analysiere mit Gemini Flash…
          (kann 30-60s dauern)
        </p>
      </div>
    );
  }

  if (!data?.available) {
    return (
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
          10-Q Analyse
        </h3>
        <p className="text-xs text-[var(--text-muted)]">
          {data?.error || "Nicht verfügbar"}
        </p>
      </div>
    );
  }

  const signalColor =
    data.overall_signal === "BULLISH"
      ? "text-[var(--accent-green)]"
    : data.overall_signal === "BEARISH"
      ? "text-[var(--accent-red)]"
    : data.overall_signal === "GEMISCHT"
      ? "text-amber-400"
    : "text-[var(--text-muted)]";

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            10-Q Tonalitäts-Diff
          </h3>
          <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
            via {data.model_used || 'DeepSeek'} · Cache 24h
          </p>
        </div>
        {data.overall_signal && (
          <span className={`text-sm font-bold ${signalColor}`}>
            {data.overall_signal}
          </span>
        )}
      </div>
      <div className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap max-h-[600px] overflow-y-auto">
        {data.diff_text}
      </div>
    </div>
  );
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
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewDecision, setReviewDecision] = useState<TradeReviewDecision | null>(null);
  const [executionLoading, setExecutionLoading] = useState(false);

  // Feature 6: 10-Q Filing Diff
  const [filingDiff, setFilingDiff] = useState<FilingDiffData | null>(null);
  const [filingDiffLoading, setFilingDiffLoading] = useState(false);

  const [onWatchlist, setOnWatchlist] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [overrideTicker, setOverrideTicker] = useState("");
  const [showOverrideInput, setShowOverrideInput] = useState(false);

  // Feature 1: Score Delta
  const [scoreDelta, setScoreDelta] = useState<ScoreDeltaData | null>(null);

  // Feature 2: Chart Analysis
  const [chartAnalysis, setChartAnalysis] = useState<ChartAnalysisData | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const chartLoadingRef = useRef(false);

  // Feature 3: Peer Comparison
  const [peerData, setPeerData] = useState<PeerComparisonData | null>(null);
  const [peerLoading, setPeerLoading] = useState(false);

  // Feature 4: VWAP Intraday
  const [vwapData, setVwapData] = useState<{
    vwap: number | null;
    vwap_delta_pct: number | null;
    above_vwap: boolean | null;
    is_market_hours: boolean;
  } | null>(null);

  // Feature 5: Options OI
  const [oiData, setOiData] = useState<OptionsOiData | null>(null);
  const [oiLoading, setOiLoading] = useState(false);

  const loadOiData = useCallback(async () => {
    if (!ticker || oiLoading) return;
    setOiLoading(true);
    try {
      const d = await fetch(
        `/api/data/options-oi/${ticker}` 
      ).then(r => r.json());
      setOiData(d);
    } catch {}
    finally { setOiLoading(false); }
  }, [tickerUpper]);

  useEffect(() => {
    setOiData(null);
  }, [tickerUpper]);

  // Feature 6: 10-Q Filing Diff
  const loadFilingDiff = useCallback(async () => {
    if (filingDiffLoading) return;
    setFilingDiffLoading(true);
    try {
      const d = await fetch(
        `/api/data/filing-diff/${ticker}` 
      ).then(r => r.json());
      setFilingDiff(d);
    } catch {}
    finally { setFilingDiffLoading(false); }
  }, [ticker]);

  const handleReviewTrade = useCallback(async () => {
    if (reviewLoading) return;

    setReviewOpen(true);
    setReviewLoading(true);
    setReviewError(null);
    setReviewDecision(null);

    try {
      const result = await api.reviewTrade(tickerUpper);
      if (!result || result.status !== "success" || !result.decision) {
        throw new Error(result?.message || "Keine Trade-Entscheidung erhalten");
      }
      setReviewDecision(result.decision as TradeReviewDecision);
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setReviewLoading(false);
    }
  }, [reviewLoading, tickerUpper]);

  const handleExecuteReviewTrade = useCallback(async () => {
    if (!reviewDecision) return;

    const recommendation = String(reviewDecision.recommendation || "").toLowerCase();
    const canExecute = recommendation.includes("buy") || recommendation.includes("short");
    if (!canExecute) {
      setReviewError("Diese Empfehlung ist nicht für eine direkte Ausführung vorgesehen.");
      return;
    }

    const direction: "long" | "short" = recommendation.includes("short") ? "short" : "long";
    const tradeReason = direction === "short" ? "Torpedo erkannt" : "Relative Stärke";

    setExecutionLoading(true);
    setReviewError(null);

    try {
      await api.manualTrade({
        ticker: tickerUpper,
        direction,
        trade_reason: tradeReason,
        opportunity_score: reviewDecision.opportunity_score ?? data?.opportunity_score ?? 5,
        torpedo_score: reviewDecision.torpedo_score ?? data?.torpedo_score ?? 5,
        notes: reviewDecision.execution_note ?? reviewDecision.reasoning ?? null,
      });
      setReviewOpen(false);
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setExecutionLoading(false);
    }
  }, [data?.opportunity_score, data?.torpedo_score, reviewDecision, tickerUpper]);

  // Feature 3: Position Sizer
  const [accountSize, setAccountSize] = useState<number>(() => {
    try {
      const saved = localStorage.getItem("kafin_account_size");
      return saved ? parseFloat(saved) : 10000;
    } catch { return 10000; }
  });
  const [riskPercent, setRiskPercent] = useState<number>(() => {
    try {
      const saved = localStorage.getItem("kafin_risk_pct");
      return saved ? parseFloat(saved) : 1;
    } catch { return 1; }
  });
  const [stopLoss, setStopLoss] = useState<number>(() => {
    try {
      const saved = localStorage.getItem("kafin_stop_pct");
      return saved ? parseFloat(saved) : 5;
    } catch { return 5; }
  });

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

  // Account Size aus localStorage laden
  useEffect(() => {
    try {
      const saved = localStorage.getItem("kafin_account_size");
      if (saved) {
        setAccountSize(parseFloat(saved));
      }
    } catch {}
  }, []);

  // Account Size speichern bei Änderung
  useEffect(() => {
    try {
      localStorage.setItem("kafin_account_size", accountSize.toString());
    } catch {}
  }, [accountSize]);

  // Risk Percent speichern bei Änderung
  useEffect(() => {
    try {
      localStorage.setItem("kafin_risk_pct", riskPercent.toString());
    } catch {}
  }, [riskPercent]);

  // Stop Loss speichern bei Änderung
  useEffect(() => {
    try {
      localStorage.setItem("kafin_stop_pct", stopLoss.toString());
    } catch {}
  }, [stopLoss]);

  const loadData = useCallback(async (forceRefresh = false) => {
    if (forceRefresh) {
      cacheInvalidate(`research:${tickerUpper}`);
    }
    
    if (!forceRefresh) {
      const cached = cacheGet<ResearchData>(`research:${tickerUpper}`);
      if (cached) {
        const normalizedCached = normalizeResearchData(cached);
        setData(normalizedCached);
        setOnWatchlist(normalizedCached.is_watchlist);
        setLoading(false);
        if (normalizedCached.last_audit) {
          setAiReport(normalizedCached.last_audit.report_text);
          setAiDate(normalizedCached.last_audit.date);
        }
        return;
      }
    }

    if (forceRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const rawResult = await api.getResearchDashboard(
        tickerUpper,
        forceRefresh,
        overrideTicker || undefined,
      );
      const result = normalizeResearchData(rawResult);
      setData(result);
      setOnWatchlist(result.is_watchlist);
      cacheSet(`research:${tickerUpper}`, result, 600);
      
      // ATR als Stop-Loss Vorschlag (nur wenn noch nie manuell gesetzt)
      if (result.atr_14 && result.price && result.price > 0) {
        const atrPct = (result.atr_14 / result.price) * 100;
        const rounded = Math.round(atrPct * 10) / 10; // eine Nachkommastelle
        const neverSaved = !localStorage.getItem("kafin_stop_pct");
        if (neverSaved) setStopLoss(rounded);
      }
      
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
  }, [tickerUpper, overrideTicker]);

  const contextSnapshot = useMemo(() => {
    if (!data) return {};
    return {
      price: data.price,
      opportunity_score: data.opportunity_score,
      torpedo_score: data.torpedo_score,
      recommendation: data.recommendation,
      atr_14: data.atr_14,
      iv_atm: data.iv_atm,
      expected_move_pct: data.expected_move_pct,
      rsi: data.rsi,
      trend: data.trend,
      report_text: data.last_audit?.report_text ?? "",
    };
  }, [data]);

  const loadScoreDelta = useCallback(async () => {
    try {
      const delta = await api.getScoreDelta(tickerUpper);
      setScoreDelta(delta);
    } catch (e: any) {
      console.warn("Score-Delta konnte nicht geladen werden:", e?.message);
    }
  }, [tickerUpper]);

  const loadChartAnalysis = useCallback(async () => {
    if (chartLoadingRef.current || chartLoading) return;
    chartLoadingRef.current = true;
    setChartLoading(true);
    try {
      const analysis = await api.getChartAnalysis(tickerUpper);
      setChartAnalysis(analysis);
    } catch (e: any) {
      console.warn("Chart-Analyse konnte nicht geladen werden:", e?.message);
    } finally {
      chartLoadingRef.current = false;
      setChartLoading(false);
    }
  }, [tickerUpper, chartLoading]);

  const loadPeerData = useCallback(async () => {
    if (!data?.company_profile?.peers?.length) return;
    setPeerLoading(true);
    try {
      const result = await api.getPeerComparison(tickerUpper);
      setPeerData(result);
    } catch (e: any) {
      console.warn("Peer-Daten nicht geladen:", e?.message);
    } finally {
      setPeerLoading(false);
    }
  }, [tickerUpper, data?.company_profile?.peers]);

  // VWAP nur laden wenn Markt offen könnte sein
  useEffect(() => {
    if (!tickerUpper) return;
    fetch(`/api/data/vwap/${tickerUpper}`)
      .then(r => r.json())
      .then(d => setVwapData(d))
      .catch(() => {});
    // Refresh alle 2 Minuten
    const id = setInterval(() => {
      fetch(`/api/data/vwap/${tickerUpper}`)
        .then(r => r.json())
        .then(d => setVwapData(d))
        .catch(() => {});
    }, 120000);
    return () => clearInterval(id);
  }, [tickerUpper]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { loadScoreDelta(); }, [loadScoreDelta]);
  useEffect(() => { loadPeerData(); }, [loadPeerData]);

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
  // (Ersetzt durch EarningsContextBanner)

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
            className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-1.5 text-sm font-mono text-[var(--text-primary)] focus:border-[var(--accent-blue)] outline-none"
          />
          <button
            onClick={() => { setShowOverrideInput(false); loadData(true); }}
            disabled={!overrideTicker.trim()}
            className="rounded-lg bg-[var(--accent-blue)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-40"
          >
            Laden
          </button>
          <button
            onClick={() => { setOverrideTicker(""); setShowOverrideInput(false); }}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-muted)]"
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
      <div className="flex items-center gap-2">
        <RefreshCw size={16} className="animate-spin text-[var(--accent-blue)]" />
        <span className="text-sm text-[var(--text-muted)]">
          Lade Research-Daten für {tickerUpper}...
        </span>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
      <div className="text-xs text-[var(--text-muted)] mt-4">
        Erste Anfrage kann 20-30 Sekunden dauern (Datenaggregation)...
      </div>
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
            {(data.pre_market_price || data.post_market_price) && (
              <span className={`text-xs font-mono ml-2 ${
                (data.pre_market_change ?? 0) >= 0
                  ? "text-[var(--accent-green)]"
                  : "text-[var(--accent-red)]"
              }`}>
                Pre: ${(data.pre_market_price || data.post_market_price)?.toFixed(2)}
                {data.pre_market_change != null && (
                  <span>
                    {" "}({data.pre_market_change >= 0 ? "+" : ""}
                    {data.pre_market_change.toFixed(2)}%)
                  </span>
                )}
              </span>
            )}
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">
            {data.company_name}
            {data.asset_type && data.asset_type !== "stock" && (
              <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded font-medium ${
                data.asset_type === "etf" 
                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                  : "bg-purple-500/20 text-purple-400 border border-purple-500/30"
              }`}>
                {data.asset_type.toUpperCase()}
              </span>
            )}
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
            className={`flex items-center gap-1.5
                        rounded-lg px-3 py-1.5 text-xs
                        font-semibold border transition-all
                        disabled:opacity-50 ${
              onWatchlist
                ? "border-[var(--accent-green)]/40 bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--accent-green)]/40 hover:text-[var(--accent-green)]"
            }`}
          >
            {watchlistLoading
              ? "..."
              : onWatchlist
                ? "✓ In Watchlist"
                : "+ Watchlist"
            }
          </button>
        </div>
      </div>

      {/* ── Timestamp ─────────────────────────────────────── */}
      <p className="text-[10px] text-[var(--text-muted)]">
        <Clock size={10} className="inline mr-1" />
        Stand: {fmt.date(data.fetched_at)} {new Date(data.fetched_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
      </p>

      {/* ── AI Chat (immer zuerst) ──────────────────────────── */}
      {data && (
        <TickerChatBlock
          ticker={tickerUpper}
          contextSnapshot={contextSnapshot}
        />
      )}

      {/* Score-Block — immer zuerst sichtbar */}
      <ScoreBlock data={data} delta={scoreDelta} />

      {/* Sentiment-Block */}
      <SentimentBlock data={data} />

      {/* Trade Setup Block */}
      <TradeSetupBlock 
        ticker={tickerUpper}
        data={chartAnalysis}
        loading={chartLoading}
        onLoad={loadChartAnalysis}
      />

      {/* ── Earnings-Kontext — vollständig */}
      <EarningsContextBanner data={data} />

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
          <StatCell label="52W Hoch" value={fmt.usd(data.fifty_two_week_high)} sub={data.distance_52w_high_pct ? `${data.distance_52w_high_pct.toFixed(1)}% entfernt` : undefined} />
          <StatCell label="52W Tief" value={fmt.usd(data.fifty_two_week_low)} />
          <StatCell label="Market Cap" value={fmt.cap(data.market_cap)} />
          <StatCell label="Beta" value={fmt.num(data.beta)} sub="Marktkorrelation" />
          <StatCell label="Div. Yield" value={data.dividend_yield ? `${(data.dividend_yield * 100).toFixed(2)}%` : "—"} />
        </div>
        
        {/* 52-Week Price Range Visualization */}
        <div className="mt-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
            52-Wochen Preisspanne
          </p>
          <PriceRangeBar 
            current={data.price || 0}
            low52w={data.fifty_two_week_low || 0}
            high52w={data.fifty_two_week_high || 0}
            ticker={data.ticker}
          />
        </div>
      </div>

      {/* Relative Stärke */}
      <RelativeStrengthBlock data={data} />

      {/* Peer-Vergleich */}
      <PeerComparisonBlock
        mainTicker={tickerUpper}
        data={peerData}
        loading={peerLoading}
      />

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
        
        {/* PEG Ratio Gauge Visualization */}
        {data.peg_ratio != null && data.peg_ratio >= 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--border)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3 text-center">
              PEG Ratio Bewertung
            </p>
            <PEGGauge pegRatio={data.peg_ratio} />
          </div>
        )}
      </div>

      {/* Block 3: Technisches Bild + Analyst */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
            Technisches Bild
          </p>

          {/* Trend-Zusammenfassung — eine Zeile */}
          <div className={`rounded-lg px-3 py-2 mb-3 text-sm
                     font-medium ${
            data.trend === "uptrend"
              ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
              : data.trend === "downtrend"
              ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
              : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
          }`}>
            {data.trend === "uptrend" ? "↑ Aufwärtstrend"
             : data.trend === "downtrend" ? "↓ Abwärtstrend"
             : "→ Seitwärts"}
            {data.sma50_distance_pct != null && (
              <span className="text-xs ml-2 font-normal opacity-80">
                {data.sma50_distance_pct > 0 ? "+" : ""}
                {data.sma50_distance_pct.toFixed(1)}% vs SMA50
                {data.sma200_distance_pct != null && (
                  <> · {data.sma200_distance_pct > 0 ? "+" : ""}
                  {data.sma200_distance_pct.toFixed(1)}% vs SMA200</>
                )}
              </span>
            )}
          </div>

          {/* 2×2 Grid: die 4 wichtigsten Signale */}
          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatCell label="RSI (14)"
              value={
                <span className={
                  data.rsi == null ? "text-[var(--text-muted)]"
                  : data.rsi > 70 ? "text-[var(--accent-red)]"
                  : data.rsi < 30 ? "text-[var(--accent-green)]"
                  : "text-[var(--text-primary)]"
                }>
                  {fmt.num(data.rsi)}
                </span>
              }
              sub={
                data.rsi != null
                  ? data.rsi > 70 ? "überkauft"
                  : data.rsi < 30 ? "überverkauft"
                  : "neutral"
                  : undefined
              }
            />
            <StatCell label="MACD"
              value={
                <span className={
                  data.macd_bullish == null
                    ? "text-[var(--text-muted)]"
                  : data.macd_bullish
                    ? "text-[var(--accent-green)]"
                    : "text-[var(--accent-red)]"
                }>
                  {data.macd_bullish == null ? "—"
                   : data.macd_bullish
                   ? "Bullish Cross" : "Bearish Cross"}
                </span>
              }
              sub={
                data.macd != null
                  ? `Wert: ${data.macd.toFixed(3)}` 
                  : undefined
              }
            />
            <StatCell label="OBV Trend"
              value={
                <span className={
                  data.obv_trend === "steigend"
                    ? "text-[var(--accent-green)]"
                  : data.obv_trend === "fallend"
                    ? "text-[var(--accent-red)]"
                  : "text-[var(--text-muted)]"
                }>
                  {data.obv_trend === "steigend" ? "↑ Käufer"
                   : data.obv_trend === "fallend" ? "↓ Verkäufer"
                   : "—"}
                </span>
              }
              sub="5T Volumentrend"
            />
            <StatCell label="RVOL"
              value={
                <span className={
                  data.rvol == null
                    ? "text-[var(--text-muted)]"
                  : data.rvol >= 1.5
                    ? "text-[var(--accent-green)]"
                  : data.rvol < 0.5
                    ? "text-[var(--text-muted)]"
                    : "text-[var(--text-primary)]"
                }>
                  {data.rvol != null ? `${data.rvol.toFixed(2)}×` : "—"}
                </span>
              }
              sub={
                data.rvol != null
                  ? data.rvol >= 1.5 ? "erhöhte Aktivität"
                  : "normales Volumen"
                  : undefined
              }
            />
          </div>

          {/* VWAP Badge */}
          {vwapData?.vwap != null && (
            <div className="flex items-center gap-2 mb-3 p-3 bg-[var(--bg-tertiary)] rounded-lg">
              <span className="text-[10px] text-[var(--text-muted)]
                            uppercase tracking-wider">
                VWAP
              </span>
              <span className="text-sm font-mono font-semibold
                            text-[var(--text-primary)]">
                ${vwapData.vwap.toFixed(2)}
              </span>
              {vwapData.vwap_delta_pct != null && (
                <span className={`text-xs font-mono ${
                  vwapData.above_vwap
                    ? "text-[var(--accent-green)]"
                    : "text-[var(--accent-red)]"
                }`}>
                  {vwapData.vwap_delta_pct >= 0 ? "+" : ""}
                  {vwapData.vwap_delta_pct.toFixed(2)}%
                </span>
              )}
              {!vwapData.is_market_hours && (
                <span className="text-[10px]
                              text-[var(--text-muted)]">
                  (Markt geschlossen)
                </span>
              )}
            </div>
          )}

          {/* ATR + Preisspanne als Kontext-Zeile */}
          <div className="flex items-center justify-between
                          text-xs text-[var(--text-muted)]
                          bg-[var(--bg-tertiary)] rounded-lg px-3 py-2">
            <span>
              ATR (14):{" "}
              <span className="font-mono text-[var(--text-primary)]">
                {data.atr_14 != null ? `$${data.atr_14.toFixed(2)}` : "—"}
              </span>
              {" "}— erwartete Tagesbewegung
            </span>
            {data.fifty_two_week_high && data.fifty_two_week_low
              && data.price && (
              <span>
                52W-Position:{" "}
                <span className="font-mono text-[var(--text-primary)]">
                  {(
                    ((data.price - data.fifty_two_week_low)
                    / (data.fifty_two_week_high - data.fifty_two_week_low))
                    * 100
                  ).toFixed(0)}%
                </span>
                {" "}der Jahresspanne
              </span>
            )}
          </div>

          {/* TD Indikatoren */}
          {data.adx_14 != null && (
            <div className="flex items-center justify-between py-1.5
                            border-b border-[var(--border)]">
              <span className="text-xs text-[var(--text-muted)]">
                ADX (Trendstärke)
              </span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-semibold
                                 text-[var(--text-primary)]">
                  {data.adx_14.toFixed(1)}
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                  data.adx_trend_strength === "strong"
                    ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                    : data.adx_trend_strength === "weak"
                      ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
                      : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                }`}>
                  {data.adx_trend_strength === "strong"   ? "Stark"
                    : data.adx_trend_strength === "moderate" ? "Moderat"
                    : "Schwach"}
                </span>
              </div>
            </div>
          )}

          {data.stoch_k != null && (
            <div className="flex items-center justify-between py-1.5
                            border-b border-[var(--border)]">
              <span className="text-xs text-[var(--text-muted)]">
                Stochastic %K/%D
              </span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-semibold
                                 text-[var(--text-primary)]">
                  {data.stoch_k.toFixed(0)} / {data.stoch_d?.toFixed(0) ?? "—"}
                </span>
                {data.stoch_signal && data.stoch_signal !== "neutral" && (
                  <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                    data.stoch_signal === "bullish_cross" || data.stoch_signal === "oversold"
                      ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                      : "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
                  }`}>
                    {data.stoch_signal === "bullish_cross" ? "↑ Kreuz"
                      : data.stoch_signal === "bearish_cross" ? "↓ Kreuz"
                      : data.stoch_signal === "oversold" ? "Überverkauft"
                      : "Überkauft"}
                  </span>
                )}
              </div>
            </div>
          )}

          {data.iv_percentile != null && (
            <div className="flex items-center justify-between py-1.5
                            border-b border-[var(--border)]">
              <span className="text-xs text-[var(--text-muted)]">
                IV Percentile
                {!data.td_enriched && (
                  <span className="ml-1 text-[9px] text-[var(--text-muted)] opacity-60">
                    (approximiert)
                  </span>
                )}
              </span>
              <span className={`text-xs font-mono font-semibold ${
                data.iv_percentile > 75
                  ? "text-[var(--accent-red)]"
                  : data.iv_percentile < 25
                    ? "text-[var(--accent-green)]"
                    : "text-[var(--text-primary)]"
              }`}>
                {data.iv_percentile.toFixed(0)}%
              </span>
            </div>
          )}
        </div>

        <div className="card p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
            Volumen & Marktstruktur
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-5">
            <StatCell label="Avg. Volumen" value={
              data.avg_volume
                ? data.avg_volume >= 1e6
                  ? `${(data.avg_volume / 1e6).toFixed(1)}M` 
                  : `${(data.avg_volume / 1e3).toFixed(0)}K` 
                : "—"
            } sub="20-Tage-Ø" />
            <StatCell label="Free Float" value={
              data.float_shares
                ? data.float_shares >= 1e9
                  ? `${(data.float_shares / 1e9).toFixed(2)}B` 
                  : `${(data.float_shares / 1e6).toFixed(0)}M` 
                : "—"
            } sub="handelbare Aktien" />
            <StatCell label="Bid-Ask" value={
              data.bid_ask_spread != null
                ? `$${data.bid_ask_spread.toFixed(3)}` 
                : "—"
            } sub="Spread" />
            <StatCell label="RVOL" value={
              <span className={
                data.rvol == null ? "text-[var(--text-muted)]"
                : data.rvol >= 1.5 ? "text-[var(--accent-green)]"
                : "text-[var(--text-primary)]"
              }>
                {data.rvol != null ? `${data.rvol.toFixed(2)}x` : "—"}
              </span>
            } sub={data.rvol != null && data.rvol >= 1.5 ? "⚡ erhöhte Aktivität" : "normal"} />
            <StatCell label="ATR (14)" value={
              data.atr_14 != null ? `$${data.atr_14.toFixed(2)}` : "—"
            } sub="erwartete Tagesbewegung" />
          </div>
          
          {/* Volume Profile Visualization */}
          <div className="mt-4 pt-4 border-t border-[var(--border)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3">
              Volumen-Profil
            </p>
            <VolumeProfile ticker={data.ticker} />
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
            <StatCell label="Put/Call Ratio" value={data.put_call_ratio ? data.put_call_ratio.toFixed(2) : "—"} />
            <StatCell label="Exp. Move" value={
              data.expected_move_pct != null
                ? `±${data.expected_move_pct.toFixed(1)}%` 
                : "—"
            } sub={data.expected_move_usd != null ? `±$${data.expected_move_usd.toFixed(2)}` : undefined} />
            {data.max_pain != null && data.price != null && (
              <div className="col-span-2 mt-3 pt-3 border-t border-[var(--border)]">
                <p className="text-[10px] text-[var(--text-muted)]
                               uppercase tracking-wider mb-2">
                  Max Pain (nächster Verfall)
                </p>
                <div className="flex items-center gap-3">
                  <span className="text-lg font-bold font-mono
                                   text-[var(--text-primary)]">
                    ${data.max_pain.toFixed(2)}
                  </span>
                  <span className={`text-xs ${
                    Math.abs(data.price - data.max_pain)
                      / data.price < 0.03
                      ? "text-amber-400"
                      : "text-[var(--text-muted)]"
                  }`}>
                    {data.price > data.max_pain
                      ? `↓ ${((data.price - data.max_pain)
                          / data.price * 100).toFixed(1)}%
                          über Max Pain`
                      : `↑ ${((data.max_pain - data.price)
                          / data.price * 100).toFixed(1)}%
                          unter Max Pain`}
                  </span>
                </div>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">
                  Magnetisches Level — Market Maker Gravitation
                  zum Verfallstag
                </p>
              </div>
            )}
            <StatCell label="Short Int." value={data.short_interest_pct != null ? `${data.short_interest_pct.toFixed(1)}%` : "—"} sub={data.squeeze_risk ? `Squeeze: ${data.squeeze_risk}` : undefined} />
          </div>
        </div>
      </div>

      {/* Options OI Strike-Heatmap */}
      <OptionsOiBlock
        data={oiData}
        currentPrice={data.price}
        onLoad={loadOiData}
        loading={oiLoading}
      />

      {/* Trade prüfen */}
      <button
        onClick={handleReviewTrade}
        disabled={reviewLoading}
        className="rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Trade prüfen
      </button>

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
          {Array.isArray(data.quarterly_history) && data.quarterly_history.length > 0 ? (
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
          {Array.isArray(data.news_bullets) && data.news_bullets.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--text-muted)] mb-2">
                Aktuelle News
              </p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {/* Material Events zuerst */}
                {data.news_bullets.some(n => n.is_material) && (
                  <div className="mb-3 rounded-lg
                                  border border-[var(--accent-red)]/30
                                  bg-[var(--accent-red)]/5 px-3 py-2">
                    <p className="text-[10px] font-semibold
                                  text-[var(--accent-red)]
                                  uppercase tracking-wider mb-1.5">
                      ⚡ Material Events
                    </p>
                    {data.news_bullets
                      .filter(n => n.is_material)
                      .map((n, i) => (
                        <p key={i}
                           className="text-xs text-[var(--accent-red)]
                                      leading-relaxed mb-1">
                          {n.text}
                        </p>
                      ))}
                  </div>
                )}

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

      {/* Position Sizer Block */}
      <PositionSizerBlock
        currentPrice={data.price || 0}
        accountSize={accountSize}
        riskPercent={riskPercent}
        stopLoss={stopLoss}
        atr={data.atr_14 ?? undefined}
        target1={chartAnalysis?.target_1 ?? undefined}
        ivAtm={data.iv_atm ?? undefined}
        expectedMovePct={data.expected_move_pct ?? undefined}
        onAccountSizeChange={setAccountSize}
        onRiskPercentChange={setRiskPercent}
        onStopLossChange={setStopLoss}
      />

      {/* Company Profile Block (P1c) */}
      <CompanyProfileBlock
        profile={data.company_profile}
        ticker={tickerUpper}
      />

      {/* 10-Q Filing Diff Block */}
      <FilingDiffBlock
        data={filingDiff}
        loading={filingDiffLoading}
        onLoad={loadFilingDiff}
      />

      {/* ══════════════════════════════════════════════════════
          UNTERER TEIL: KI-ANALYSE
      ══════════════════════════════════════════════════════ */}
      
      {/* ── Interaktiver Chart ──────────────────────────── */}
      <ChartAnalysisSection
        ticker={tickerUpper}
        expectedMovePct={data.expected_move_pct ?? undefined}
        currentPrice={data.price ?? undefined}
      />

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
              } disabled:cursor-not-allowed`}
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

      {reviewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-6">
          <div className="w-full max-w-3xl rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">Trade-Entscheidung</h2>
                <p className="text-xs text-[var(--text-muted)]">Reasoner-Review für {tickerUpper}</p>
              </div>
              <button
                onClick={() => setReviewOpen(false)}
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                Schließen
              </button>
            </div>

            <div className="space-y-4 px-6 py-5">
              {reviewLoading && <p className="text-sm text-[var(--text-muted)]">Lade Entscheidung...</p>}

              {reviewError && (
                <div className="rounded-lg border border-[var(--accent-red)]/40 bg-[var(--accent-red)]/10 px-4 py-3 text-sm text-[var(--accent-red)]">
                  {reviewError}
                </div>
              )}

              {reviewDecision && !reviewLoading && (
                <>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-[var(--border)] p-4">
                      <p className="text-xs text-[var(--text-muted)]">Empfehlung</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                        {(reviewDecision.recommendation_label || reviewDecision.recommendation || "—").toUpperCase()}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[var(--border)] p-4">
                      <p className="text-xs text-[var(--text-muted)]">Opportunity Score</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--accent-green)]">
                        {reviewDecision.opportunity_score?.toFixed(1) ?? "—"}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[var(--border)] p-4">
                      <p className="text-xs text-[var(--text-muted)]">Torpedo Score</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--accent-red)]">
                        {reviewDecision.torpedo_score?.toFixed(1) ?? "—"}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3 rounded-xl border border-[var(--border)] p-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Begründung</p>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-primary)]">
                        {reviewDecision.reasoning || reviewDecision.execution_note || reviewDecision.decision_text || "Keine Begründung verfügbar."}
                      </p>
                    </div>

                    {reviewDecision.key_bull_points?.length ? (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Bullische Punkte</p>
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--text-primary)]">
                          {reviewDecision.key_bull_points.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </div>
                    ) : null}

                    {reviewDecision.key_risks?.length ? (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Risiken</p>
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--text-primary)]">
                          {reviewDecision.key_risks.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </div>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap justify-end gap-3">
                    <button
                      onClick={() => setReviewOpen(false)}
                      className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    >
                      Schließen
                    </button>
                    <button
                      onClick={handleExecuteReviewTrade}
                      disabled={executionLoading || !reviewDecision || !String(reviewDecision.recommendation || "").toLowerCase().includes("buy") && !String(reviewDecision.recommendation || "").toLowerCase().includes("short")}
                      className="rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {executionLoading ? "Ausführen..." : "Trade ausführen"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
