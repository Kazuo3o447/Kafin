import { ArrowDownRight, ArrowUpRight, Info } from "lucide-react";

type IndexData = {
  name: string;
  price?: number;
  change_1d_pct?: number;
  rsi_14?: number;
  trend?: string;
  error?: string;
};

type SectorRank = { symbol: string; name: string; perf_5d: number };

type MacroSnapshot = {
  regime?: string;
  fed_rate?: number;
  vix?: number;
  credit_spread_bps?: number;
  yield_curve_10y_2y?: number;
  dxy?: number;
};

type WatchlistItem = {
  ticker: string;
  company_name?: string;
  notes?: string;
  opportunity_score?: number;
  torpedo_score?: number;
  price?: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(endpoint: string, revalidate = 60): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function getDashboardData() {
  try {
    const [macro, overview, report, watchlist] = await Promise.all([
      fetchJSON<MacroSnapshot>("/api/data/macro", 120),
      fetchJSON<{ indices: Record<string, IndexData>; sector_ranking_5d: SectorRank[]; macro: Record<string, IndexData> }>(
        "/api/data/market-overview",
        120
      ),
      fetchJSON<{ report?: string }>("/api/reports/latest", 30).catch(() => ({ report: "" })),
      fetchJSON<WatchlistItem[]>("/api/watchlist", 30).catch(() => []),
    ]);

    return { macro, overview, report: report.report || "Noch kein Briefing.", watchlist };
  } catch (error) {
    console.error("Dashboard fetch error", error);
    return {
      macro: {},
      overview: { indices: {}, sector_ranking_5d: [], macro: {} },
      report: "API nicht erreichbar.",
      watchlist: [] as WatchlistItem[],
    };
  }
}

function TrendIcon({ value }: { value?: number }) {
  if (value === undefined || value === null) return <Info size={14} className="text-[var(--text-muted)]" />;
  return value >= 0 ? (
    <ArrowUpRight size={16} className="text-[var(--accent-green)]" />
  ) : (
    <ArrowDownRight size={16} className="text-[var(--accent-red)]" />
  );
}

function formatPct(value?: number, fallback = "--") {
  if (value === undefined || value === null || Number.isNaN(value)) return fallback;
  const formatted = value.toFixed(2).replace("-0.00", "0.00");
  return `${formatted}%`;
}

function MacroBanner({ macro }: { macro: MacroSnapshot }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-gradient-to-r from-[#1c1c2d] to-[#11111b] p-6 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-[var(--text-muted)]">Regime</p>
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">{macro.regime?.toUpperCase() || "CAUTIOUS"}</h2>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-5">
          {[
            { label: "Fed", value: macro.fed_rate ? `${macro.fed_rate.toFixed(2)}%` : "-" },
            { label: "VIX", value: macro.vix ? macro.vix.toFixed(2) : "-" },
            { label: "Spread", value: macro.credit_spread_bps ? `${macro.credit_spread_bps.toFixed(2)} bp` : "-" },
            { label: "Yield", value: macro.yield_curve_10y_2y ? `${macro.yield_curve_10y_2y.toFixed(2)}%` : "-" },
            { label: "DXY", value: macro.dxy ? macro.dxy.toFixed(2) : "-" },
          ].map((item) => (
            <div key={item.label}>
              <p className="text-[10px] uppercase tracking-[0.3em] text-[var(--text-muted)]">{item.label}</p>
              <p className="text-base font-semibold text-[var(--text-primary)]">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IndexCards({ data }: { data: Record<string, IndexData> }) {
  const entries = Object.entries(data);
  if (!entries.length) return null;
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {entries.map(([symbol, item]) => (
        <div key={symbol} className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-[var(--text-muted)]">{item.name}</p>
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">{symbol}</h3>
            </div>
            <TrendIcon value={item.change_1d_pct} />
          </div>
          <div className="mt-4 flex items-end justify-between">
            <div>
              <p className="text-2xl font-bold text-[var(--text-primary)]">${item.price?.toFixed(2) || "--"}</p>
              <p className={`text-sm ${item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
                {formatPct(item.change_1d_pct)} (1d)
              </p>
            </div>
            <div className="text-right text-xs text-[var(--text-muted)]">
              <p>RSI {item.rsi_14 ? item.rsi_14.toFixed(1) : "--"}</p>
              <p className="capitalize">{item.trend || "-"}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SectorTable({ sectors }: { sectors: SectorRank[] }) {
  if (!sectors.length) return null;
  const top = sectors.slice(0, 5);
  const bottom = sectors.slice(-5).reverse();
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
        <h4 className="text-sm font-semibold text-[var(--text-secondary)]">Top Sektoren (5d)</h4>
        <div className="mt-4 space-y-2 text-sm">
          {top.map((item) => (
            <div key={item.symbol} className="flex items-center justify-between">
              <span className="text-[var(--text-primary)]">{item.name}</span>
              <span className="text-[var(--accent-green)]">{formatPct(item.perf_5d)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
        <h4 className="text-sm font-semibold text-[var(--text-secondary)]">Schwächste Sektoren</h4>
        <div className="mt-4 space-y-2 text-sm">
          {bottom.map((item) => (
            <div key={item.symbol} className="flex items-center justify-between">
              <span className="text-[var(--text-primary)]">{item.name}</span>
              <span className="text-[var(--accent-red)]">{formatPct(item.perf_5d)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MacroProxies({ macro }: { macro: Record<string, IndexData> }) {
  if (!Object.keys(macro).length) return null;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <h4 className="text-sm font-semibold text-[var(--text-secondary)]">Makro-Proxys</h4>
      <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Object.entries(macro).map(([symbol, item]) => (
          <div key={symbol} className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3 text-sm">
            <div className="flex items-center justify-between text-[var(--text-muted)]">
              <span>{item.name}</span>
              <TrendIcon value={item.change_1d_pct} />
            </div>
            <div className="mt-2 text-lg font-semibold text-[var(--text-primary)]">${item.price?.toFixed(2) || "--"}</div>
            <p className={`${item.change_1d_pct && item.change_1d_pct >= 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"}`}>
              {formatPct(item.change_1d_pct)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function BriefingPreview({ report }: { report: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--text-muted)]">Morning Briefing</p>
          <h3 className="text-xl font-semibold text-[var(--text-primary)]">Letzter Run</h3>
        </div>
        <button className="rounded-full border border-[var(--border)] px-4 py-1 text-xs uppercase tracking-[0.2em] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]">
          Volltext öffnen
        </button>
      </div>
      <div className="mt-4 max-h-48 overflow-y-auto rounded-lg bg-[var(--bg-tertiary)] p-4 font-mono text-sm text-[var(--text-secondary)]">
        {report.slice(0, 1200) || "Noch kein Report generiert."}
      </div>
    </div>
  );
}

function WatchlistGrid({ items }: { items: WatchlistItem[] }) {
  if (!items.length) return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5 text-sm text-[var(--text-muted)]">
      Watchlist leer – füge im Watchlist-Tab Ticker hinzu.
    </div>
  );

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--text-muted)]">Watchlist</p>
          <h3 className="text-xl font-semibold text-[var(--text-primary)]">Aktive Ticker</h3>
        </div>
        <span className="text-sm text-[var(--text-muted)]">{items.length} Symbole</span>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.slice(0, 9).map((item) => (
          <div key={item.ticker} className="rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[var(--text-muted)]">{item.company_name || ""}</p>
                <h4 className="text-lg font-semibold text-[var(--text-primary)]">{item.ticker}</h4>
              </div>
              <div className="text-right">
                <p className="text-sm text-[var(--text-secondary)]">${item.price?.toFixed(2) || "--"}</p>
                <p className="text-[10px] text-[var(--text-muted)]">OS: {item.opportunity_score ?? "--"} | TS: {item.torpedo_score ?? "--"}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-[var(--text-muted)] line-clamp-2">{item.notes || "Keine Notiz."}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default async function Home() {
  const { macro, overview, report, watchlist } = await getDashboardData();

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Command Center</p>
          <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Morning Situation Briefing</h1>
          <p className="text-sm text-[var(--text-secondary)]">Makro → Indizes → Watchlist. Alles auf einen Blick.</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-muted)]">
          <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--accent-green)]" />
          Live verbunden mit Kafin Backend
        </div>
      </div>

      <MacroBanner macro={macro} />

      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-[var(--text-muted)]">Marktstruktur</h2>
        <IndexCards data={overview.indices} />
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <SectorTable sectors={overview.sector_ranking_5d || []} />
          <MacroProxies macro={overview.macro} />
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <BriefingPreview report={report} />
        <WatchlistGrid items={watchlist} />
      </section>
    </div>
  );
}
