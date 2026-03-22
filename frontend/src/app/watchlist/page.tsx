"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { Plus, Trash2, Search, AlertTriangle, Clock, Sparkles, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { cachedFetch, cacheGet, cacheAge, cacheInvalidate } from "@/lib/clientCache";
import { CacheStatus } from "@/components/CacheStatus";

type WatchlistItem = {
  ticker: string;
  company_name?: string;
  sector?: string;
  notes?: string;
  opportunity_score?: number | null;
  torpedo_score?: number | null;
  opp_delta?: number | null;       // gestern
  torp_delta?: number | null;      // gestern
  week_opp_delta?: number | null;  // diese Woche
  week_torp_delta?: number | null; // diese Woche
  price?: number | null;
  change_pct?: number | null;      // 1T
  change_5d_pct?: number | null;   // 5T — NEU
  pre_market_price?: number | null;
  pre_market_change?: number | null;
  post_market_price?: number | null;
  market_cap_b?: number | null;
  earnings_date?: string | null;
  earnings_countdown?: number | null;
  report_timing?: string | null;   // NEU
  recommendation?: string | null;
  rsi?: number | null;
  trend?: string | null;
  above_sma50?: boolean | null;    // NEU
  atr_14?: number | null;          // NEU
  rvol?: number | null;            // NEU
  iv_atm?: number | null;          // NEU
  web_prio?: number | null;
  finbert_sentiment?: number | null;
  sentiment_label?: string | null;
  sentiment_trend?: string | null;
  has_material_news?: boolean | null;
  sentiment_count?: number | null;
};

// Sorting and filtering types
type SortField = "opportunity_score" | "torpedo_score" | "change_pct" | "change_5d_pct" | "earnings_countdown" | "rvol" | "week_opp_delta";
type SortDir = "asc" | "desc";
type ActiveFilter = null | "earnings_7d" | "torpedo_high" | "rvol_spike" | "sma_break" | "improving";

function buildAlerts(watchlist: WatchlistItem[]): {
  ticker: string;
  type: "earnings_urgent"|"earnings_soon"|"torpedo_rising"|
        "sma_break"|"rvol_spike"|"setup_improving"
      |"material_news"|"sentiment_drop";
  message: string;
  color: "red"|"amber"|"green";
}[] {
  const alerts: ReturnType<typeof buildAlerts> = [];

  for (const item of watchlist) {
    const t = item.ticker;

    // 1. Earnings ≤5T — kritisch
    if (item.earnings_countdown != null
        && item.earnings_countdown >= 0
        && item.earnings_countdown <= 5) {
      const timing =
        item.report_timing === "pre_market" ? "Pre-Market"
        : item.report_timing === "after_market" ? "After-Market"
        : "";
      const em = item.iv_atm
        ? ` · Expected Move ±${(item.iv_atm / 10).toFixed(1)}%` 
        : "";
      alerts.push({
        ticker: t,
        type: "earnings_urgent",
        message: `Earnings in ${item.earnings_countdown === 0
          ? "HEUTE" : item.earnings_countdown + " Tagen"}`
          + (timing ? ` · ${timing}` : "") + em,
        color: "red",
      });
    }

    // 2. Torpedo-Delta stark gestiegen diese Woche
    if (item.week_torp_delta != null
        && item.week_torp_delta >= 1.5) {
      alerts.push({
        ticker: t,
        type: "torpedo_rising",
        message: `Torpedo-Score +${item.week_torp_delta.toFixed(1)}` 
          + " diese Woche — Risiko steigt",
        color: "red",
      });
    }

    // 3. SMA50-Bruch
    if (item.above_sma50 === false
        && item.trend === "downtrend") {
      alerts.push({
        ticker: t,
        type: "sma_break",
        message: "Unter SMA50 gefallen — technischer Bruch",
        color: "red",
      });
    }

    // 4. RVOL Spike
    if (item.rvol != null && item.rvol >= 2.0) {
      alerts.push({
        ticker: t,
        type: "rvol_spike",
        message: `RVOL ${item.rvol.toFixed(1)}× — erhöhte Aktivität`,
        color: "green",
      });
    }

    // 5. Earnings ≤14T (amber)
    if (item.earnings_countdown != null
        && item.earnings_countdown > 5
        && item.earnings_countdown <= 14) {
      alerts.push({
        ticker: t,
        type: "earnings_soon",
        message: `Earnings in ${item.earnings_countdown} Tagen` 
          + (item.report_timing === "pre_market" ? " · Pre-Market"
             : item.report_timing === "after_market" ? " · After-Market"
             : ""),
        color: "amber",
      });
    }

    // 6. Setup stark verbessert
    if (item.week_opp_delta != null
        && item.week_opp_delta >= 1.5
        && (item.week_torp_delta == null
            || item.week_torp_delta <= 0)) {
      alerts.push({
        ticker: t,
        type: "setup_improving",
        message: `Opp-Score +${item.week_opp_delta.toFixed(1)}` 
          + " diese Woche — Setup verbessert",
        color: "green",
      });
    }

    // 7. Material News erkannt
    if (item.has_material_news === true) {
      alerts.push({
        ticker: t,
        type: "material_news",
        message: "⚡ Material Event — kursrelevant",
        color: "red",
      });
    }

    // 8. Sentiment-Bruch
    if (item.sentiment_trend === "deteriorating"
        && item.finbert_sentiment != null
        && item.finbert_sentiment > 0.1) {
      alerts.push({
        ticker: t,
        type: "sentiment_drop",
        message: "Sentiment dreht bearish bei positivem Niveau",
        color: "amber",
      });
    }
  }

  // Sortierung: rot zuerst, dann amber, dann grün
  const order = { red: 0, amber: 1, green: 2 };
  alerts.sort((a, b) => order[a.color] - order[b.color]);

  return alerts.slice(0, 7); // max 7 Alerts
}

function AlertStrip({
  alerts,
}: {
  alerts: ReturnType<typeof buildAlerts>;
}) {
  if (alerts.length === 0) return null;

  const colorMap = {
    red:   { bg: "bg-[var(--accent-red)]/8",
             border: "border-l-[var(--accent-red)]",
             dot: "bg-[var(--accent-red)]",
             text: "text-[var(--accent-red)]" },
    amber: { bg: "bg-amber-500/8",
             border: "border-l-amber-500",
             dot: "bg-amber-500",
             text: "text-amber-400" },
    green: { bg: "bg-[var(--accent-green)]/8",
             border: "border-l-[var(--accent-green)]",
             dot: "bg-[var(--accent-green)]",
             text: "text-[var(--accent-green)]" },
  };

  return (
    <div className="card p-4 border-l-4 border-l-[var(--accent-red)]">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-semibold uppercase
                      tracking-[0.25em] text-[var(--text-muted)]">
          Heute aufpassen
        </p>
        <span className="text-[10px] text-[var(--text-muted)]">
          automatisch aus Watchlist-Daten
        </span>
      </div>
      <div className="space-y-1.5">
        {alerts.map((alert, i) => {
          const c = colorMap[alert.color];
          return (
            <div
              key={i}
              className={`flex items-center gap-3 rounded-lg
                          px-3 py-2 border-l-2
                          ${c.bg} ${c.border}`}
            >
              <div className={`w-1.5 h-1.5 rounded-full
                               shrink-0 ${c.dot}`} />
              <Link
                href={`/research/${alert.ticker}`}
                className={`text-xs font-semibold
                            hover:underline ${c.text}`}
              >
                {alert.ticker}
              </Link>
              <span className="text-xs text-[var(--text-secondary)]">
                {alert.message}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WatchlistOverview({
  watchlist,
}: {
  watchlist: WatchlistItem[];
}) {
  if (watchlist.length === 0) return null;

  const earningsThisWeek = watchlist.filter(
    (w) => w.earnings_countdown != null
      && w.earnings_countdown >= 0
      && w.earnings_countdown <= 7
  );
  const earningsTickers = earningsThisWeek
    .map((w) => w.ticker).join(" · ");

  const avgOpp = watchlist
    .filter((w) => w.opportunity_score != null)
    .reduce((s, w) => s + (w.opportunity_score || 0), 0)
    / (watchlist.filter((w) => w.opportunity_score != null).length || 1);

  const avgOppDelta = watchlist
    .filter((w) => w.week_opp_delta != null)
    .reduce((s, w) => s + (w.week_opp_delta || 0), 0)
    / (watchlist.filter((w) => w.week_opp_delta != null).length || 1);

  const highTorpedo = watchlist.filter(
    (w) => w.torpedo_score != null && w.torpedo_score >= 6
  ).length;

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {[
        {
          label: "Ticker gesamt",
          value: watchlist.length.toString(),
          sub: null,
          color: "text-[var(--text-primary)]",
        },
        {
          label: "Earnings diese Woche",
          value: earningsThisWeek.length.toString(),
          sub: earningsTickers || null,
          color: earningsThisWeek.length > 0
            ? "text-amber-400" : "text-[var(--text-primary)]",
        },
        {
          label: "Ø Opportunity-Score",
          value: avgOpp.toFixed(1),
          sub: avgOppDelta !== 0
            ? `${avgOppDelta > 0 ? "↑" : "↓"} ${
                avgOppDelta > 0 ? "+" : ""
              }${avgOppDelta.toFixed(1)} diese Woche`
            : null,
          color: avgOpp >= 6
            ? "text-[var(--accent-green)]"
            : avgOpp >= 4 ? "text-amber-400"
            : "text-[var(--accent-red)]",
        },
        {
          label: "Torpedo ≥6",
          value: highTorpedo.toString(),
          sub: highTorpedo > 0 ? "Positionen prüfen" : "Alles ruhig",
          color: highTorpedo > 0
            ? "text-[var(--accent-red)]"
            : "text-[var(--accent-green)]",
        },
      ].map((card) => (
        <div key={card.label}
             className="card p-4 text-center">
          <p className="text-[10px] uppercase tracking-[0.25em]
                        text-[var(--text-muted)] mb-1">
            {card.label}
          </p>
          <p className={`text-2xl font-bold ${card.color}`}>
            {card.value}
          </p>
          {card.sub && (
            <p className={`text-[10px] mt-1 ${card.color} opacity-80`}>
              {card.sub}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function FilterBar({
  active,
  onChange,
  watchlist,
}: {
  active: ActiveFilter;
  onChange: (f: ActiveFilter) => void;
  watchlist: WatchlistItem[];
}) {
  const counts = {
    earnings_7d: watchlist.filter(
      (w) => w.earnings_countdown != null
        && w.earnings_countdown >= 0
        && w.earnings_countdown <= 7
    ).length,
    torpedo_high: watchlist.filter(
      (w) => w.torpedo_score != null && w.torpedo_score >= 6
    ).length,
    rvol_spike: watchlist.filter(
      (w) => w.rvol != null && w.rvol >= 1.5
    ).length,
    sma_break: watchlist.filter((w) => w.above_sma50 === false).length,
    improving: watchlist.filter(
      (w) => w.week_opp_delta != null && w.week_opp_delta >= 1.0
    ).length,
  };

  const filters: {
    key: ActiveFilter; label: string; count: number;
    color: string; activeColor: string;
  }[] = [
    {
      key: "earnings_7d",
      label: "Earnings ≤7T",
      count: counts.earnings_7d,
      color: "border-amber-500/30 text-amber-400",
      activeColor: "bg-amber-500/20 border-amber-500",
    },
    {
      key: "torpedo_high",
      label: "Torpedo ≥6",
      count: counts.torpedo_high,
      color: "border-[var(--accent-red)]/30 text-[var(--accent-red)]",
      activeColor: "bg-[var(--accent-red)]/15 border-[var(--accent-red)]",
    },
    {
      key: "rvol_spike",
      label: "RVOL >1.5×",
      count: counts.rvol_spike,
      color: "border-[var(--accent-green)]/30 text-[var(--accent-green)]",
      activeColor: "bg-[var(--accent-green)]/15 border-[var(--accent-green)]",
    },
    {
      key: "sma_break",
      label: "SMA50 gebrochen",
      count: counts.sma_break,
      color: "border-[var(--accent-red)]/30 text-[var(--accent-red)]",
      activeColor: "bg-[var(--accent-red)]/15 border-[var(--accent-red)]",
    },
    {
      key: "improving",
      label: "Setup ↑ Woche",
      count: counts.improving,
      color: "border-[var(--accent-green)]/30 text-[var(--accent-green)]",
      activeColor: "bg-[var(--accent-green)]/15 border-[var(--accent-green)]",
    },
  ];

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <button
        onClick={() => onChange(null)}
        className={`text-xs px-3 py-1.5 rounded-full border
                    transition-all ${
          active === null
            ? "bg-[var(--accent-blue)]/15 border-[var(--accent-blue)] text-[var(--accent-blue)]"
            : "border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]"
        }`}
      >
        Alle ({watchlist.length})
      </button>
      {filters.map((f) => (
        <button
          key={f.key}
          onClick={() => onChange(active === f.key ? null : f.key)}
          disabled={f.count === 0}
          className={`text-xs px-3 py-1.5 rounded-full border
                      transition-all disabled:opacity-30 ${
            active === f.key
              ? f.activeColor
              : `${f.color} hover:bg-[var(--bg-tertiary)]` 
          }`}
        >
          {f.label}
          {f.count > 0 && (
            <span className="ml-1.5 opacity-70">({f.count})</span>
          )}
        </button>
      ))}
    </div>
  );
}

function SectorHeatmap({
  sectorDistribution,
  concentrationWarning,
}: {
  sectorDistribution: Record<string, number>;
  concentrationWarning: string | null;
}) {
  const total = Object.values(sectorDistribution)
    .reduce((s, v) => s + v, 0);
  if (total === 0) return null;

  const COLORS: Record<string, string> = {
    Technology:            "#2563eb",
    Healthcare:            "#059669",
    Financials:            "#7c3aed",
    "Consumer Discretionary": "#d97706",
    "Consumer Staples":    "#65a30d",
    Industrials:           "#0891b2",
    Energy:                "#dc2626",
    Materials:             "#9f1239",
    "Real Estate":         "#92400e",
    Utilities:             "#4338ca",
    "Communication Services": "#be185d",
    Unknown:               "#475569",
  };

  const sorted = Object.entries(sectorDistribution)
    .sort(([, a], [, b]) => b - a);

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-semibold uppercase
                      tracking-[0.25em] text-[var(--text-muted)]">
          Sektor-Verteilung
        </p>
        {concentrationWarning && (
          <span className="text-[10px] text-amber-400
                           bg-amber-500/10 px-2 py-0.5 rounded-full">
            Klumpenrisiko
          </span>
        )}
      </div>
      <div className="flex h-3 rounded-full overflow-hidden gap-px mb-3">
        {sorted.map(([sector, count]) => (
          <div
            key={sector}
            title={`${sector}: ${((count / total) * 100).toFixed(0)}%`}
            style={{
              width: `${(count / total) * 100}%`,
              background: COLORS[sector] || COLORS.Unknown,
              minWidth: "4px",
            }}
          />
        ))}
      </div>
      <div className="flex gap-x-4 gap-y-1 flex-wrap">
        {sorted.map(([sector, count]) => (
          <div key={sector} className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-sm shrink-0"
              style={{
                background: COLORS[sector] || COLORS.Unknown,
              }}
            />
            <span className="text-[10px] text-[var(--text-muted)]">
              {sector}{" "}
              <span className="text-[var(--text-secondary)]">
                {((count / total) * 100).toFixed(0)}%
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTicker, setNewTicker] = useState({ ticker: "", company_name: "", sector: "", notes: "" });
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [dataAge, setDataAge] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [sectorDistribution, setSectorDistribution] = useState<Record<string, number>>({});
  const [concentrationWarning, setConcentrationWarning] = useState<string | null>(null);

  const [sortField, setSortField] = useState<SortField>("opportunity_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>(null);
  const [marketContext, setMarketContext] = useState<{
    fear_greed_score: number | null;
    fear_greed_label: string | null;
    regime: string | null;
  } | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && showAddModal) closeModal();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showAddModal]);

  // Sortier- + Filterlogik
  const processedList = useMemo(() => {
    let list = [...watchlist];

    // Suche
    if (search) {
      list = list.filter(
        (w) =>
          w.ticker.toLowerCase().includes(search.toLowerCase())
          || (w.company_name || "").toLowerCase()
              .includes(search.toLowerCase())
      );
    }

    // Filter
    if (activeFilter === "earnings_7d") {
      list = list.filter(
        (w) => w.earnings_countdown != null
          && w.earnings_countdown >= 0
          && w.earnings_countdown <= 7
      );
    } else if (activeFilter === "torpedo_high") {
      list = list.filter(
        (w) => w.torpedo_score != null && w.torpedo_score >= 6
      );
    } else if (activeFilter === "rvol_spike") {
      list = list.filter(
        (w) => w.rvol != null && w.rvol >= 1.5
      );
    } else if (activeFilter === "sma_break") {
      list = list.filter((w) => w.above_sma50 === false);
    } else if (activeFilter === "improving") {
      list = list.filter(
        (w) => w.week_opp_delta != null && w.week_opp_delta >= 1.0
      );
    }

    // Sortierung
    list.sort((a, b) => {
      const av = a[sortField] ?? (sortDir === "desc" ? -Infinity : Infinity);
      const bv = b[sortField] ?? (sortDir === "desc" ? -Infinity : Infinity);
      return sortDir === "desc"
        ? (bv as number) - (av as number)
        : (av as number) - (bv as number);
    });

    return list;
  }, [watchlist, search, sortField, sortDir, activeFilter]);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  }

  function SortHeader({
    field, label, align = "right",
  }: {
    field: SortField; label: string; align?: string;
  }) {
    const active = sortField === field;
    const alignClass =
      align === "left"   ? "text-left"
      : align === "center" ? "text-center"
      : "text-right";
    return (
      <th
        onClick={() => toggleSort(field)}
        className={`px-3 py-3 ${alignClass} font-semibold
                    text-[var(--text-secondary)] cursor-pointer
                    select-none hover:text-[var(--text-primary)]
                    transition-colors ${active
                      ? "text-[var(--accent-blue)]" : ""}`}
      >
        {label}
        {active && (
          <span className="ml-1 text-[var(--accent-blue)]">
            {sortDir === "desc" ? "↓" : "↑"}
          </span>
        )}
      </th>
    );
  }

  const alerts = useMemo(
    () => buildAlerts(watchlist),
    [watchlist]
  );

  useEffect(() => {
    loadWatchlist();
  }, []);

  useEffect(() => {
    Promise.all([
      fetch("/api/data/fear-greed").then(r => r.json()),
      fetch("/api/data/macro").then(r => r.json()),
    ]).then(([fg, macro]) => {
      setMarketContext({
        fear_greed_score:  fg?.score ?? null,
        fear_greed_label:  fg?.label ?? null,
        regime: macro?.regime ?? null,
      });
    }).catch(() => {});
  }, []);

  const loadWatchlist = useCallback(async (invalidate = false) => {
    if (invalidate) {
      cacheInvalidate('watchlist:enriched');
      setRefreshing(true);
    }

    // Sofort gecachte Daten anzeigen (kein Ladescreen wenn Cache vorhanden)
    const cached = cacheGet<any>("watchlist:enriched");
    if (cached && !invalidate) {
      setWatchlist(cached.watchlist || []);
      setSectorDistribution(cached.sector_distribution || {});
      setConcentrationWarning(cached.concentration_warning || null);
      setLoading(false);
      setFromCache(true);
      setDataAge(cacheAge("watchlist:enriched"));
      return; // Cache ist frisch genug — kein API-Call
    }

    if (!invalidate) setLoading(true);

    try {
      const { data, fromCache: isCached } = await cachedFetch("watchlist:enriched", () => api.getWatchlistEnriched(), 300);
      setWatchlist(data?.watchlist || []);
      setSectorDistribution(data?.sector_distribution || {});
      setConcentrationWarning(data?.concentration_warning || null);
      setFromCache(isCached);
      setDataAge(cacheAge("watchlist:enriched"));
    } catch (error) {
      console.error("Watchlist fetch error", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  async function handleAddTicker() {
    const ticker = newTicker.ticker.trim().toUpperCase();

    // Validierung
    if (!ticker) {
      setAddError("Ticker darf nicht leer sein.");
      return;
    }
    if (!/^[A-Z]{1,5}$/.test(ticker)) {
      setAddError("Ungültiger Ticker — nur Buchstaben, max. 5 Zeichen (z.B. AAPL).");
      return;
    }

    setAddLoading(true);
    setAddError(null);

    try {
      await api.addTicker({
        ticker,
        company_name: newTicker.company_name || ticker,
        sector: newTicker.sector || "Unknown",
        notes: newTicker.notes || "",
      });
      // Erfolg
      closeModal();
      cacheInvalidate("watchlist:enriched");
      // Optimistic: Sofort den neuen Ticker hinzufügen
      setWatchlist(prev => [...prev, {
        ticker,
        company_name: newTicker.company_name || ticker,
        sector: newTicker.sector || "Unknown",
        notes: newTicker.notes || "",
        web_prio: null,
        price: undefined,
        change_pct: undefined,
        opportunity_score: undefined,
        torpedo_score: undefined,
        recommendation: undefined,
      }]);
    } catch (err: any) {
      const msg = err?.message || "";
      if (msg.includes("409") || msg.toLowerCase().includes("duplicate")) {
        setAddError(`${ticker} ist bereits auf der Watchlist.`);
      } else if (msg.includes("422")) {
        setAddError("Ungültige Eingabe — prüfe den Ticker.");
      } else if (msg.includes("404")) {
        setAddError("API-Endpoint nicht erreichbar — Backend läuft?");
      } else {
        setAddError(`Fehler beim Hinzufügen: ${msg || "Unbekannter Fehler"}`);
      }
    } finally {
      setAddLoading(false);
    }
  }

  function closeModal() {
    setShowAddModal(false);
    setNewTicker({ ticker: "", company_name: "", sector: "", notes: "" });
    setAddError(null);
    setAddLoading(false);
  }

  async function handleRemoveTicker(ticker: string) {
    if (!confirm(`${ticker} wirklich entfernen?`)) return;
    try {
      await api.removeTicker(ticker);
      cacheInvalidate('watchlist:enriched');
      // Optimistic: Sofort den Ticker entfernen
      setWatchlist(prev => prev.filter(item => item.ticker !== ticker));
    } catch (error) {
      console.error("Remove ticker error", error);
    }
  }

  async function handleUpdateWebPrio(
    ticker: string,
    prio: number | null
  ) {
    try {
      await api.updateWebPrio(ticker, prio);
      cacheInvalidate("watchlist:list");
      cacheInvalidate("watchlist:enriched");
      // Optimistic Update wird direkt im onChange gemacht
    } catch (error) {
      console.error("Web Prio update error", error);
      // Bei Fehler: State zurücksetzen
      setWatchlist(prev => prev.map(w => 
        w.ticker === ticker 
          ? { ...w, web_prio: w.web_prio } // Originalwert behalten
          : w
      ));
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="card p-4 animate-pulse"
          >
            <div className="flex items-center
                           justify-between">
              <div className="flex items-center gap-3">
                <div className="h-8 w-14 rounded-lg
                                 bg-[var(--bg-tertiary)]" />
                <div className="space-y-1.5">
                  <div className="h-3 w-24
                                   bg-[var(--bg-tertiary)]
                                   rounded" />
                  <div className="h-2.5 w-16
                                   bg-[var(--bg-tertiary)]
                                   rounded" />
                </div>
              </div>
              <div className="flex gap-3">
                <div className="h-8 w-12 rounded-lg
                                 bg-[var(--bg-tertiary)]" />
                <div className="h-8 w-12 rounded-lg
                                 bg-[var(--bg-tertiary)]" />
              </div>
            </div>
          </div>
        ))}
        <p className="text-xs text-center
                       text-[var(--text-muted)] pt-2">
          Kursdaten werden geladen…
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-12">

      {/* Header — unverändert */}
      <div className="flex flex-col gap-4 lg:flex-row
                      lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Watchlist</p>
          <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Alle Ticker</h1>
          <p className="text-sm text-[var(--text-secondary)]">{watchlist.length} Symbole unter Beobachtung</p>
        </div>
        <CacheStatus fromCache={fromCache} ageSeconds={dataAge} onRefresh={() => loadWatchlist(true)} refreshing={refreshing || loading} />
        <div className="flex gap-2">
          <button
            onClick={async () => {
              try {
                const result = await api.runWebIntelligenceBatch();
                alert(`Web Intelligence Batch: ${result.processed} verarbeitet`);
              } catch {
                alert("Batch fehlgeschlagen — TAVILY_API_KEY gesetzt?");
              }
            }}
            className="flex items-center gap-2 rounded-lg border
                       border-[var(--border)] px-4 py-2 text-sm
                       font-medium text-[var(--text-secondary)]
                       hover:bg-[var(--bg-tertiary)] transition-all"
            title="Web Intelligence für alle Ticker aktualisieren"
          >
            🌐 Web-Scan
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus size={16} />
            Ticker hinzufügen
          </button>
        </div>
      </div>

      {/* Market Context Banner */}
      {marketContext && (
        <div className="flex items-center gap-3
                         flex-wrap py-2 px-1 mb-2">
          {marketContext.regime && (
            <span className="rounded-full px-3 py-1
                              text-[10px] font-semibold
                              uppercase tracking-wider
                              bg-[var(--bg-tertiary)]
                              text-[var(--text-muted)]">
              {marketContext.regime}
            </span>
          )}
          {marketContext.fear_greed_score != null && (
            <span className={`rounded-full px-3 py-1
                               text-[10px] font-semibold ${
              (marketContext.fear_greed_score ?? 50) <= 25
                ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
              : (marketContext.fear_greed_score ?? 50) >= 75
                ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
              : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
            }`}>
              F&G {Math.round(marketContext.fear_greed_score)}
              {" — "}{marketContext.fear_greed_label}
            </span>
          )}
        </div>
      )}

      {/* 1. Alert-Streifen */}
      <AlertStrip alerts={alerts} />

      {/* 2. Überblick-Kacheln */}
      <WatchlistOverview watchlist={watchlist} />

      {/* 3. Sektor-Heatmap */}
      <SectorHeatmap
        sectorDistribution={sectorDistribution}
        concentrationWarning={concentrationWarning}
      />

      {/* 4. Suche + Filter-Leiste */}
      <div className="flex flex-col gap-3 sm:flex-row
                      sm:items-center">
        <div className="flex w-full items-center gap-2 rounded-lg 
                        border border-[var(--border)] 
                        bg-[var(--bg-secondary)] px-4 py-2">
          <Search size={16} className="text-[var(--text-muted)] shrink-0" />
          <input
            type="text"
            placeholder="Ticker oder Name suchen..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-transparent text-sm text-[var(--text-primary)] 
                       outline-none placeholder:text-[var(--text-muted)]"
          />
        </div>
      </div>
      <FilterBar
        active={activeFilter}
        onChange={setActiveFilter}
        watchlist={watchlist}
      />

      {/* 5. Haupttabelle */}
      <div className="overflow-x-auto rounded-xl border
                border-[var(--border)] bg-[var(--bg-secondary)]">
        <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
          <thead className="border-b border-[var(--border)]
                      bg-[var(--bg-tertiary)]">
            <tr>
              <th className="px-3 py-3 text-left font-semibold
                             text-[var(--text-secondary)] w-28">
                Ticker
              </th>
              <th className="px-3 py-3 text-left font-semibold
                             text-[var(--text-secondary)]">
                Name
              </th>
              <SortHeader field="change_pct" label="1T%" />
              <SortHeader field="change_5d_pct" label="5T%" />
              <SortHeader field="opportunity_score" label="Opp / Torp" align="center" />
              <th className="px-3 py-3 text-center font-semibold
                             text-[var(--text-secondary)] w-24">
                Δ Woche
              </th>
              <SortHeader field="earnings_countdown" label="Earnings" align="center" />
              <SortHeader field="rvol" label="RVOL" />
              <th className="px-3 py-3 text-right font-semibold
                             text-[var(--text-secondary)] w-16">
                ATR
              </th>
              <th className="px-3 py-3 text-center font-semibold
                             text-[var(--text-secondary)] w-20">
                Signal
              </th>
              <th className="px-3 py-3 text-center font-semibold
                             text-[var(--text-secondary)] w-20">
                Sentiment
              </th>
              <th className="px-3 py-3 text-center font-semibold
                             text-[var(--text-secondary)] w-24">
                Web-Prio
              </th>
              <th className="px-3 py-3 w-10" />
            </tr>
          </thead>
          <tbody>
            {processedList.map((item, idx) => {
              // Zeilen-Hintergrund
              const rowBg =
                (item.torpedo_score != null && item.torpedo_score >= 7)
                || item.above_sma50 === false
                  ? "bg-[var(--accent-red)]/3 hover:bg-[var(--accent-red)]/6"
                : item.earnings_countdown != null
                  && item.earnings_countdown >= 0
                  && item.earnings_countdown <= 7
                  ? "bg-amber-500/3 hover:amber-500/6"
                : "hover:bg-[var(--bg-tertiary)]";

              const pctColor = (v?: number | null) =>
                v == null ? "text-[var(--text-muted)]"
                : v > 0 ? "text-[var(--accent-green)]"
                : "text-[var(--accent-red)]";

              const fmtPct = (v?: number | null) =>
                v == null ? "—"
                : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

              // Opp/Torp Balken-Breite
              const oppW = Math.min(100, (item.opportunity_score || 0) * 10);
              const torpW = Math.min(100, (item.torpedo_score || 0) * 10);
              const torpColor =
                (item.torpedo_score || 0) >= 7 ? "#E24B4A"
                : (item.torpedo_score || 0) >= 4 ? "#BA7517"
                : "#639922";

              return (
                <tr key={`${item.ticker}-${idx}`}
                    className={`border-b border-[var(--border)] ${rowBg}`}>

                  {/* Ticker */}
                  <td className="px-3 py-3">
                    <Link
                      href={`/research/${item.ticker}`}
                      className="font-semibold font-mono text-sm
                                 text-[var(--accent-blue)] hover:underline"
                    >
                      {item.ticker}
                    </Link>
                    {item.above_sma50 === false && (
                      <span className="ml-1 text-[10px]
                                        text-[var(--accent-red)]">
                        ✗SMA
                      </span>
                    )}
                    {item.earnings_countdown != null
                     && item.earnings_countdown >= 0
                     && item.earnings_countdown <= 7 && (
                      <span className="ml-1 text-[10px] text-amber-400">
                        ⚡
                      </span>
                    )}
                  </td>

                  {/* Name */}
                  <td className="px-3 py-3">
                    <p className="text-xs text-[var(--text-primary)]
                                   truncate max-w-[140px]">
                      {item.company_name || "—"}
                    </p>
                    <p className="text-[10px] text-[var(--text-muted)]">
                      {item.sector || "—"}
                    </p>
                  </td>

                  {/* 1T% */}
                  <td className={`px-3 py-3 text-right text-xs
                                   font-mono font-semibold
                                   ${pctColor(item.change_pct)}`}>
                    {fmtPct(item.change_pct)}
                    {/* Pre-Market */}
                    {item.pre_market_price != null
                     && item.pre_market_change != null && (
                      <div className="flex items-center gap-1 mt-1">
                        <span className="text-[9px]
                                           text-[var(--text-muted)]">
                          PRE
                        </span>
                        <span className={`text-[10px] font-mono
                                            font-semibold ${
                          item.pre_market_change >= 0
                            ? "text-[var(--accent-green)]"
                            : "text-[var(--accent-red)]"
                        }`}>
                          {item.pre_market_change >= 0 ? "+" : ""}
                          {item.pre_market_change.toFixed(2)}%
                        </span>
                      </div>
                    )}
                    {/* Post-Market (wenn kein Pre-Market) */}
                    {item.pre_market_price == null
                     && item.post_market_price != null && (
                      <div className="flex items-center gap-1 mt-1">
                        <span className="text-[9px]
                                           text-[var(--text-muted)]">
                          POST
                        </span>
                        <span className="text-[10px] font-mono
                                            font-semibold
                                            text-[var(--text-muted)]">
                          ${item.post_market_price.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </td>

                  {/* 5T% */}
                  <td className={`px-3 py-3 text-right text-xs
                                   font-mono
                                   ${pctColor(item.change_5d_pct)}`}>
                    {fmtPct(item.change_5d_pct)}
                  </td>

                  {/* Opp / Torp mit Mini-Balken */}
                  <td className="px-3 py-3">
                    <div className="flex items-center justify-center gap-2">
                      <span className={`text-sm font-semibold font-mono ${
                        (item.opportunity_score || 0) >= 7
                          ? "text-[var(--accent-green)]"
                        : (item.opportunity_score || 0) >= 4
                          ? "text-amber-400"
                        : "text-[var(--accent-red)]"
                      }`}>
                        {item.opportunity_score?.toFixed(1) ?? "—"}
                      </span>
                      <span className="text-[10px]
                                        text-[var(--text-muted)]">/</span>
                      <span className={`text-sm font-semibold font-mono ${
                        (item.torpedo_score || 0) >= 7
                          ? "text-[var(--accent-red)]"
                        : (item.torpedo_score || 0) >= 4
                          ? "text-amber-400"
                        : "text-[var(--accent-green)]"
                      }`}>
                        {item.torpedo_score?.toFixed(1) ?? "—"}
                      </span>
                    </div>
                    <div className="flex gap-1 mt-1">
                      <div className="flex-1 h-1 rounded-full
                                       bg-[var(--bg-tertiary)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[var(--accent-green)]"
                          style={{ width: `${oppW}%` }}
                        />
                      </div>
                      <div className="flex-1 h-1 rounded-full
                                       bg-[var(--bg-tertiary)] overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${torpW}%`,
                            background: torpColor,
                          }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Δ Woche — Torpedo INVERTIERT */}
                  <td className="px-3 py-3 text-center">
                    {item.week_opp_delta != null && (
                      <div className={`text-[10px] ${
                        item.week_opp_delta > 0
                          ? "text-[var(--accent-green)]"
                        : item.week_opp_delta < 0
                          ? "text-[var(--accent-red)]"
                        : "text-[var(--text-muted)]"
                      }`}>
                        Opp {item.week_opp_delta > 0 ? "↑" : item.week_opp_delta < 0 ? "↓" : "→"}
                        {item.week_opp_delta > 0 ? "+" : ""}
                        {item.week_opp_delta.toFixed(1)}
                      </div>
                    )}
                    {item.week_torp_delta != null && (
                      <div className={`text-[10px] ${
                        // INVERTIERT: Torpedo steigt = rot
                        item.week_torp_delta > 0
                          ? "text-[var(--accent-red)]"
                        : item.week_torp_delta < 0
                          ? "text-[var(--accent-green)]"
                        : "text-[var(--text-muted)]"
                      }`}>
                        Torp {item.week_torp_delta > 0 ? "↑" : item.week_torp_delta < 0 ? "↓" : "→"}
                        {item.week_torp_delta > 0 ? "+" : ""}
                        {item.week_torp_delta.toFixed(1)}
                      </div>
                    )}
                    {item.week_opp_delta == null && (
                      <span className="text-[10px]
                                        text-[var(--text-muted)]">—</span>
                    )}
                  </td>

                  {/* Earnings */}
                  <td className="px-3 py-3 text-center">
                    {item.earnings_countdown == null ? (
                      <span className="text-[10px]
                                        text-[var(--text-muted)]">—</span>
                    ) : item.earnings_countdown === 0 ? (
                      <span className="text-xs font-semibold
                                        text-[var(--accent-red)]">
                        HEUTE
                      </span>
                    ) : (
                      <div>
                        <span className={`text-xs font-semibold ${
                          item.earnings_countdown <= 5
                            ? "text-[var(--accent-red)]"
                          : item.earnings_countdown <= 14
                            ? "text-amber-400"
                          : "text-[var(--text-secondary)]"
                        }`}>
                          {item.earnings_countdown}T
                        </span>
                        {item.report_timing && (
                          <div className="text-[9px]
                                          text-[var(--text-muted)]">
                            {item.report_timing === "pre_market"
                              ? "PM" : "AM"}
                          </div>
                        )}
                      </div>
                    )}
                  </td>

                  {/* RVOL */}
                  <td className="px-3 py-3 text-right">
                    <span className={`text-xs font-mono ${
                      item.rvol == null
                        ? "text-[var(--text-muted)]"
                      : item.rvol >= 2.0
                        ? "text-[var(--accent-green)] font-semibold"
                      : item.rvol >= 1.5
                        ? "text-amber-400"
                      : "text-[var(--text-secondary)]"
                    }`}>
                      {item.rvol != null
                        ? `${item.rvol.toFixed(1)}×` 
                        : "—"}
                    </span>
                  </td>

                  {/* ATR */}
                  <td className="px-3 py-3 text-right">
                    <span className="text-xs font-mono
                                     text-[var(--text-secondary)]">
                      {item.atr_14 != null
                        ? `$${item.atr_14.toFixed(2)}` 
                        : "—"}
                    </span>
                  </td>

                  {/* Signal */}
                  <td className="px-3 py-3 text-center">
                    {item.recommendation ? (
                      <span className={`text-[10px] px-2 py-1 rounded-full
                                         font-semibold ${
                        item.recommendation.toLowerCase().includes("buy")
                          ? "bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
                        : item.recommendation.toLowerCase().includes("short")
                          ? "bg-[var(--accent-red)]/10 text-[var(--accent-red)]"
                        : item.recommendation.toLowerCase().includes("watch")
                          ? "bg-amber-500/10 text-amber-400"
                        : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                      }`}>
                        {item.recommendation}
                      </span>
                    ) : (
                      <span className="text-[10px]
                                        text-[var(--text-muted)]">—</span>
                    )}
                  </td>

                  {/* Sentiment */}
                  <td className="px-3 py-3 text-center">
                    {item.finbert_sentiment != null && item.sentiment_count != null && item.sentiment_count > 0 ? (
                      <div className="flex flex-col items-center gap-1">
                        <div className={`text-xs font-mono font-semibold ${
                          item.finbert_sentiment > 0.15 ? "text-[var(--accent-green)]"
                          : item.finbert_sentiment < -0.15 ? "text-[var(--accent-red)]"
                          : "text-[var(--text-muted)]"
                        }`}>
                          {item.finbert_sentiment >= 0 ? "+" : ""}{item.finbert_sentiment.toFixed(2)}
                        </div>
                        <div className="flex items-center gap-1">
                          {item.has_material_news && (
                            <AlertTriangle size={10} className="text-[var(--accent-red)]" />
                          )}
                          <span className={`text-[9px] ${
                            item.sentiment_trend === "improving" ? "text-[var(--accent-green)]"
                            : item.sentiment_trend === "deteriorating" ? "text-[var(--accent-red)]"
                            : "text-[var(--text-muted)]"
                          }`}>
                            {item.sentiment_trend === "improving" ? "↑"
                             : item.sentiment_trend === "deteriorating" ? "↓"
                             : "→"}
                          </span>
                          <span className="text-[9px] text-[var(--text-muted)]">
                            {item.sentiment_count}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <span className="text-[10px] text-[var(--text-muted)]">—</span>
                    )}
                  </td>

                  {/* Web-Prio — unverändert */}
                  <td className="px-3 py-3 text-center">
                    <select
                      value={item.web_prio ?? "auto"}
                      onChange={(e) => {
                        const val = e.target.value;
                        const newPrio = val === "auto"
                          ? null : parseInt(val);
                        setWatchlist((prev) =>
                          prev.map((w) =>
                            w.ticker === item.ticker
                              ? { ...w, web_prio: newPrio }
                              : w
                          )
                        );
                        handleUpdateWebPrio(item.ticker, newPrio);
                      }}
                      className="rounded border border-[var(--border)]
                                 bg-[var(--bg-tertiary)] px-1.5 py-1
                                 text-[10px] text-[var(--text-primary)]
                                 outline-none"
                    >
                      <option value="auto">Auto</option>
                      <option value="1">P1 · 3×/Tag</option>
                      <option value="2">P2 · 1×/Tag</option>
                      <option value="3">P3 · Wöchentlich</option>
                      <option value="4">P4 · Pausiert</option>
                    </select>
                  </td>

                  {/* Löschen */}
                  <td className="px-3 py-3 text-center">
                    <button
                      onClick={() => handleRemoveTicker(item.ticker)}
                      className="text-[var(--text-muted)]
                                 hover:text-[var(--accent-red)]"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add Modal — bestehender Code */}
      {showAddModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}
        >
          <div className="w-full max-w-md rounded-2xl border border-[var(--border)]
                          bg-[var(--bg-secondary)] p-6 shadow-2xl">

            {/* Header */}
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                Ticker hinzufügen
              </h2>
              <button
                onClick={closeModal}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]
                           transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Felder */}
            <div className="space-y-3">

              {/* Ticker — wichtigstes Feld, hervorgehoben */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Ticker <span className="text-[var(--accent-red)]">*</span>
                </label>
                <input
                  type="text"
                  placeholder="z.B. MU, AAPL, NVDA"
                  value={newTicker.ticker}
                  onChange={(e) => {
                    setNewTicker({ ...newTicker, ticker: e.target.value.toUpperCase() });
                    setAddError(null);
                  }}
                  onKeyDown={(e) => { if (e.key === "Enter") handleAddTicker(); }}
                  autoFocus
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             font-mono font-semibold uppercase tracking-wider
                             text-[var(--text-primary)] outline-none
                             placeholder:text-[var(--text-muted)] placeholder:normal-case
                             placeholder:font-normal placeholder:tracking-normal
                             focus:border-[var(--accent-blue)]"
                />
              </div>

              {/* Firmenname — optional */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Firmenname
                  <span className="ml-1 text-[var(--text-muted)] font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Wird aus Ticker abgeleitet wenn leer"
                  value={newTicker.company_name}
                  onChange={(e) => setNewTicker({ ...newTicker, company_name: e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             text-[var(--text-primary)] outline-none
                             placeholder:text-[var(--text-muted)]
                             focus:border-[var(--accent-blue)]"
                />
              </div>

              {/* Sektor — optional */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Sektor
                  <span className="ml-1 text-[var(--text-muted)] font-normal">(optional)</span>
                </label>
                <select
                  value={newTicker.sector}
                  onChange={(e) => setNewTicker({ ...newTicker, sector: e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             text-[var(--text-primary)] outline-none
                             focus:border-[var(--accent-blue)]"
                >
                  <option value="">Sektor auswählen...</option>
                  <option value="Technology">Technology</option>
                  <option value="Healthcare">Healthcare</option>
                  <option value="Financials">Financials</option>
                  <option value="Consumer Discretionary">Consumer Discretionary</option>
                  <option value="Consumer Staples">Consumer Staples</option>
                  <option value="Industrials">Industrials</option>
                  <option value="Energy">Energy</option>
                  <option value="Materials">Materials</option>
                  <option value="Real Estate">Real Estate</option>
                  <option value="Utilities">Utilities</option>
                  <option value="Communication Services">Communication Services</option>
                  <option value="Crypto">Crypto</option>
                  <option value="Unknown">Unbekannt</option>
                </select>
              </div>

              {/* Notizen */}
              <div>
                <label className="mb-1.5 block text-xs font-medium
                                  text-[var(--text-secondary)]">
                  Notizen
                  <span className="ml-1 text-[var(--text-muted)] font-normal">(optional)</span>
                </label>
                <textarea
                  placeholder="Trading-These, Catalyst, Erinnerung..."
                  value={newTicker.notes}
                  onChange={(e) => setNewTicker({ ...newTicker, notes: e.target.value })}
                  rows={2}
                  className="w-full rounded-lg border border-[var(--border)]
                             bg-[var(--bg-tertiary)] px-4 py-2.5 text-sm
                             text-[var(--text-primary)] outline-none resize-none
                             placeholder:text-[var(--text-muted)]
                             focus:border-[var(--accent-blue)]"
                />
              </div>
            </div>

            {/* Error-Anzeige */}
            {addError && (
              <div className="mt-3 rounded-lg border border-[var(--accent-red)]/30
                              bg-[var(--accent-red)]/10 px-4 py-3 text-sm
                              text-[var(--accent-red)]">
                ⚠ {addError}
              </div>
            )}

            {/* Buttons */}
            <div className="mt-5 flex gap-3">
              <button
                onClick={handleAddTicker}
                disabled={addLoading || !newTicker.ticker.trim()}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg
                           bg-[var(--accent-blue)] px-4 py-2.5 text-sm font-semibold
                           text-white transition-all hover:opacity-90
                           disabled:cursor-not-allowed disabled:opacity-40"
              >
                {addLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2
                                    border-white/30 border-t-white" />
                    Wird hinzugefügt...
                  </>
                ) : (
                  <>+ Zur Watchlist</>
                )}
              </button>
              <button
                onClick={closeModal}
                disabled={addLoading}
                className="rounded-lg border border-[var(--border)] px-4 py-2.5
                           text-sm font-medium text-[var(--text-secondary)]
                           transition-all hover:bg-[var(--bg-tertiary)]
                           disabled:opacity-40"
              >
                Abbrechen
              </button>
            </div>

            {/* Hinweis */}
            <p className="mt-3 text-center text-xs text-[var(--text-muted)]">
              Nur Ticker ist Pflichtfeld · Escape zum Schließen
            </p>

          </div>
        </div>
      )}
    </div>
  );
}
