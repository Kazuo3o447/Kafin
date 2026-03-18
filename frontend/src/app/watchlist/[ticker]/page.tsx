import { ArrowLeft, TrendingUp, Activity, FileText, Calendar } from "lucide-react";
import Link from "next/link";
import { ChartAnalysisSection } from "./ChartAnalysisSection";
import { TrackRecordSection } from "./TrackRecordSection";
import InteractiveChart from "@/components/InteractiveChart";
import { ActionButtons } from "./ActionButtons";

type TickerDetailProps = {
  params: Promise<{ ticker: string }>;
};

type ProfileData = {
  companyName?: string;
  sector?: string;
  marketCap?: number;
  price?: number;
  error?: string;
};

type TechnicalData = {
  price?: number;
  sma_50?: number;
  sma_200?: number;
  rsi_14?: number;
  support?: number;
  resistance?: number;
  trend?: string;
};

type NewsMemory = {
  bullet_points?: Array<{
    id?: string;
    ticker?: string;
    category?: string;
    bullet_text?: string;
    sentiment_score?: number;
    is_material?: boolean;
    created_at?: string;
  }>;
};

type LongTermMemory = {
  insights?: Array<{
    id?: string;
    insight_text?: string;
    created_at?: string;
  }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function getTickerData(ticker: string) {
  try {
    const [profile, newsMemory, longTermMemory] = await Promise.all([
      fetchJSON<ProfileData>(`/api/data/company/${ticker}/profile`).catch(() => ({ error: "Profil nicht verfügbar" })),
      fetchJSON<NewsMemory>(`/api/news/memory/${ticker}`).catch(() => ({ bullet_points: [] })),
      fetchJSON<LongTermMemory>(`/api/data/long-term-memory/${ticker}`).catch(() => ({ insights: [] })),
    ]);

    return { profile, newsMemory, longTermMemory };
  } catch (error) {
    console.error("Ticker data fetch error", error);
    return {
      profile: { error: "Daten nicht verfügbar" },
      newsMemory: { bullet_points: [] },
      longTermMemory: { insights: [] },
    };
  }
}

function ProfileCard({ profile, ticker }: { profile: ProfileData; ticker: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
      <div className="flex items-center gap-2 text-[var(--text-muted)]">
        <Activity size={16} />
        <h2 className="text-sm font-semibold uppercase tracking-[0.3em]">Firmenprofil</h2>
      </div>
      <div className="mt-4 space-y-3">
        <div>
          <p className="text-xs text-[var(--text-muted)]">Ticker</p>
          <p className="text-2xl font-bold text-[var(--text-primary)]">{ticker}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-xs text-[var(--text-muted)]">Name</p>
            <p className="text-sm text-[var(--text-primary)]">{profile.companyName || "-"}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">Sektor</p>
            <p className="text-sm text-[var(--text-primary)]">{profile.sector || "-"}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">Market Cap</p>
            <p className="text-sm text-[var(--text-primary)]">
              {profile.marketCap ? `$${(profile.marketCap / 1e9).toFixed(2)}B` : "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">Aktueller Kurs</p>
            <p className="text-sm text-[var(--text-primary)]">${profile.price?.toFixed(2) || "-"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function NewsMemoryCard({ newsMemory }: { newsMemory: NewsMemory }) {
  const bullets = newsMemory.bullet_points || [];
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
      <div className="flex items-center gap-2 text-[var(--text-muted)]">
        <FileText size={16} />
        <h2 className="text-sm font-semibold uppercase tracking-[0.3em]">News-Gedächtnis</h2>
      </div>
      <div className="mt-4 max-h-96 space-y-3 overflow-y-auto">
        {bullets.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Keine News-Stichpunkte vorhanden.</p>
        ) : (
          bullets.slice(0, 20).map((item, idx) => (
            <div
              key={item.id || idx}
              className={`rounded-lg border p-3 ${
                item.is_material
                  ? "border-[var(--accent-red)] bg-red-900/10"
                  : "border-[var(--border)] bg-[var(--bg-tertiary)]"
              }`}
            >
              <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                <span className="rounded bg-[var(--bg-elevated)] px-2 py-1">{item.category || "News"}</span>
                <span
                  className={`font-semibold ${
                    (item.sentiment_score ?? 0) > 0.3
                      ? "text-[var(--accent-green)]"
                      : (item.sentiment_score ?? 0) < -0.3
                      ? "text-[var(--accent-red)]"
                      : "text-[var(--text-muted)]"
                  }`}
                >
                  Sentiment: {item.sentiment_score?.toFixed(2) || "0.00"}
                </span>
              </div>
              <p className="mt-2 text-sm text-[var(--text-primary)]">{item.bullet_text}</p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {item.created_at ? new Date(item.created_at).toLocaleDateString("de-DE") : "-"}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function LongTermMemoryCard({ longTermMemory }: { longTermMemory: LongTermMemory }) {
  const insights = longTermMemory.insights || [];
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
      <div className="flex items-center gap-2 text-[var(--text-muted)]">
        <TrendingUp size={16} />
        <h2 className="text-sm font-semibold uppercase tracking-[0.3em]">Langzeit-Gedächtnis</h2>
      </div>
      <div className="mt-4 max-h-96 space-y-3 overflow-y-auto">
        {insights.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Keine Langzeit-Insights vorhanden.</p>
        ) : (
          insights.map((item, idx) => (
            <div key={item.id || idx} className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3">
              <p className="text-sm text-[var(--text-primary)]">{item.insight_text}</p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {item.created_at ? new Date(item.created_at).toLocaleDateString("de-DE") : "-"}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default async function TickerDetailPage({ params }: TickerDetailProps) {
  const { ticker } = await params;
  const { profile, newsMemory, longTermMemory } = await getTickerData(ticker);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href="/watchlist"
          className="flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft size={16} />
          Zurück zur Watchlist
        </Link>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Ticker-Detail</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">{ticker}</h1>
        <p className="text-sm text-[var(--text-secondary)]">Vollständige Analyse und Gedächtnis</p>
      </div>

      <ProfileCard profile={profile} ticker={ticker} />

      <ActionButtons ticker={ticker} />

      <ChartAnalysisSection ticker={ticker} />

      <div className="grid gap-6 lg:grid-cols-2">
        <NewsMemoryCard newsMemory={newsMemory} />
        <LongTermMemoryCard longTermMemory={longTermMemory} />
      </div>

      <TrackRecordSection ticker={ticker} />
    </div>
  );
}
