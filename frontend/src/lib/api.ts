const API_BASE = (typeof window === "undefined" && process.env.INTERNAL_API_URL) 
  ? process.env.INTERNAL_API_URL 
  : "";

export async function fetchAPI(endpoint: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const api = {
  // Generic GET method for dynamic endpoints
  get: (endpoint: string) => fetchAPI(endpoint),

  // Watchlist
  getWatchlist: () => fetchAPI("/api/watchlist"),
  addTicker: (data: any) => fetchAPI("/api/watchlist", { method: "POST", body: JSON.stringify(data) }),
  removeTicker: (ticker: string, cleanupData?: boolean) => {
    const url = cleanupData ? `/api/watchlist/${ticker}?cleanup_data=true` : `/api/watchlist/${ticker}`;
    return fetchAPI(url, { method: "DELETE" });
  },
  updateWebPrio: (ticker: string, prio: number | null) =>
    fetchAPI(`/api/watchlist/${ticker}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ web_prio: prio }),
    }),

  // Data Cleanup
  previewTickerData: (ticker: string) => fetchAPI(`/api/data/cleanup/${ticker}/preview`),
  cleanupTickerData: (ticker: string) => fetchAPI(`/api/data/cleanup/${ticker}`, { method: "DELETE" }),

  // Reports
  generateMorningBriefing: () => fetchAPI("/api/reports/generate-morning", { method: "POST" }),
  generateSundayReport: () => fetchAPI("/api/reports/generate-sunday", { method: "POST" }),
  generateAuditReport: (ticker: string) => fetchAPI(`/api/reports/generate/${ticker}`, { method: "POST" }),
  reviewTrade: (ticker: string) => fetchAPI(`/api/reports/review-trade/${ticker}`, { method: "POST" }),
  getLatestReport: () => fetchAPI("/api/reports/latest"),
  postEarningsReview: (ticker: string) => fetchAPI(`/api/reports/post-earnings-review/${ticker}`, { method: "POST" }),

  // Data
  getMacro: () => fetchAPI("/api/data/macro"),
  getMarketOverview: () => fetchAPI("/api/data/market-overview"),
  getCompanyProfile: (ticker: string) => fetchAPI(`/api/data/company/${ticker}/profile`),
  getNewsMemory: (ticker: string) => fetchAPI(`/api/news/memory/${ticker}`),
  getLongTermMemory: (ticker: string) => fetchAPI(`/api/data/long-term-memory/${ticker}`),
  getTickerTrackRecord: (ticker: string) => fetchAPI(`/api/data/ticker-track-record/${ticker}`),
  getPerformance: () => fetchAPI("/api/data/performance"),
  getAlpacaAccount: () => fetchAPI("/api/data/alpaca/account"),
  getAlpacaPositions: () => fetchAPI("/api/data/alpaca/positions"),
  openAlpacaPaperTrade: (data: Record<string, unknown>) =>
    fetchAPI("/api/data/alpaca/paper-trade", { method: "POST", body: JSON.stringify(data) }),
  getRealTrades: (ticker?: string) =>
    fetchAPI(`/api/data/real-trades${ticker ? `?ticker=${ticker}` : ""}`),
  createRealTrade: (data: Record<string, unknown>) =>
    fetchAPI("/api/data/real-trades", { method: "POST", body: JSON.stringify(data) }),
  updateRealTrade: (id: number, data: Record<string, unknown>) =>
    fetchAPI(`/api/data/real-trades/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteRealTrade: (id: number) =>
    fetchAPI(`/api/data/real-trades/${id}`, { method: "DELETE" }),
  getDecisionSnapshots: (ticker?: string, limit = 50) =>
    fetchAPI((() => {
      const params = new URLSearchParams();
      if (ticker) params.set("ticker", ticker);
      params.set("limit", String(limit));
      const query = params.toString();
      return `/api/data/decision-snapshots${query ? `?${query}` : ""}`;
    })()),
  updateSnapshotOutcome: (id: number, data: Record<string, unknown>) =>
    fetchAPI(`/api/data/decision-snapshots/${id}/outcome`, { method: "POST", body: JSON.stringify(data) }),
  getShadowPortfolio: () => fetchAPI("/api/shadow/portfolio"),
  getShadowTrades: (status = "all") => fetchAPI(`/api/shadow/portfolio/trades?status=${status}`),
  getShadowWeeklyReport: () => fetchAPI("/api/shadow/portfolio/weekly-report"),
  manualTrade: (data: {
    ticker: string;
    direction: "long" | "short";
    trade_reason: string;
    opportunity_score?: number;
    torpedo_score?: number;
    notes?: string | null;
  }) => fetchAPI("/api/shadow/manual-trade", { method: "POST", body: JSON.stringify(data) }),

  // Actions
  runNewsScan: () => fetchAPI("/api/news/scan", { method: "POST" }),
  runNewsScanWeekend: () => fetchAPI("/api/news/scan-weekend", { method: "POST" }),
  runSecScan: () => fetchAPI("/api/news/sec-scan", { method: "POST" }),
  runMacroScan: () => fetchAPI("/api/news/macro-scan", { method: "POST" }),
  runSignalScan: () => fetchAPI("/api/signals/scan", { method: "POST" }),
  scanGoogleNews: () => fetchAPI("/api/google-news/scan"),
  setupN8n: () => fetchAPI("/api/n8n/setup", { method: "POST" }),

  // Diagnostics
  getDiagnostics: () => fetchAPI("/api/diagnostics/full"),
  getDbStatus: () => fetchAPI("/api/diagnostics/db"),
  testTelegram: () => fetchAPI("/api/telegram/test", { method: "POST" }),
  
  // Logs
  getLogs: () => fetchAPI("/api/logs"),

  // Watchlist & Opportunities
  getWatchlistEnriched: () => fetchAPI("/api/watchlist/enriched"),
  getOpportunities: (days = 7) => fetchAPI(`/api/opportunities?days=${days}`),

  // Charts
  getSparkline: (ticker: string, days = 7) => fetchAPI(`/api/data/sparkline/${ticker}?days=${days}`),
  getChartAnalysis: (ticker: string) => fetchAPI(`/api/chart-analysis/${ticker}`),
  getChartAnalysisTop: (limit = 5) => fetchAPI(`/api/chart-analysis-top?limit=${limit}`),
  getOhlcv: (ticker: string, period = "6mo", interval = "1d") =>
    fetchAPI(`/api/data/ohlcv/${ticker}?period=${period}&interval=${interval}`),
  getChartOverlays: (ticker: string) => fetchAPI(`/api/data/chart-overlays/${ticker}`),
  getQuickSnapshot: (ticker: string) => fetchAPI(`/api/data/quick-snapshot/${ticker.toUpperCase()}`),
  getEarningsRadar: (days = 14) => fetchAPI(`/api/data/earnings-radar?days=${days}`),
  getResearchDashboard: (
    ticker: string,
    forceRefresh = false,
    overrideTicker?: string,
  ) => {
    let url = `/api/data/research/${ticker.toUpperCase()}`;
    const params = new URLSearchParams();
    if (forceRefresh) params.set("force_refresh", "true");
    if (overrideTicker) params.set("override_ticker", overrideTicker);
    const qs = params.toString();
    return fetchAPI(qs ? `${url}?${qs}` : url);
  },

  // Peer Comparison
  getPeerComparison: (ticker: string) =>
    fetchAPI(`/api/data/peer-comparison/${ticker.toUpperCase()}`),

  // Watchlist Correlation
  getWatchlistCorrelation: () => fetchAPI("/api/data/watchlist-correlation"),

  // Journal
  getJournal: (ticker?: string) =>
    fetchAPI(`/api/journal${ticker ? `?ticker=${ticker}` : ""}`),
  createJournalEntry: (data: Record<string, unknown>) =>
    fetchAPI("/api/journal", { method: "POST", body: JSON.stringify(data) }),
  updateJournalEntry: (id: number, data: Record<string, unknown>) =>
    fetchAPI(`/api/journal/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteJournalEntry: (id: number) =>
    fetchAPI(`/api/journal/${id}`, { method: "DELETE" }),

  // Google News Search Terms
  getSearchTerms: () => fetchAPI("/api/google-news/search-terms"),
  addSearchTerm: (term: string, category = "custom") =>
    fetchAPI(`/api/google-news/search-terms?term=${encodeURIComponent(term)}&category=${encodeURIComponent(category)}`, {
      method: "POST",
    }),
  removeSearchTerm: (term: string) =>
    fetchAPI(`/api/google-news/search-terms?term=${encodeURIComponent(term)}`, { method: "DELETE" }),

  // Markets Dashboard
  getMarketBreadth: () => fetchAPI("/api/data/market-breadth"),
  getIntermarket: () => fetchAPI("/api/data/intermarket"),
  getMarketNewsSentiment: () => fetchAPI("/api/data/market-news-sentiment"),
  getEconomicCalendar: () => fetchAPI("/api/data/economic-calendar"),
  generateMarketAudit: () => fetchAPI("/api/market-audit", {
    method: "POST",
  }),

  // Web Intelligence
  refreshWebIntelligence: (ticker: string) =>
    fetchAPI(`/api/web-intelligence/refresh/${ticker}`, {
      method: "POST",
    }),
  runWebIntelligenceBatch: () =>
    fetchAPI("/api/web-intelligence/batch", { method: "POST" }),

  // Score Delta
  getScoreDelta: (ticker: string) => fetchAPI(`/api/data/score-delta/${ticker}`),

  // Signal Feed
  getSignalsFeed: (forceRefresh = false) =>
    fetchAPI(`/api/data/signals/feed${forceRefresh ? "?force_refresh=true" : ""}`),

  // Signal Feed Config (für Settings)
  getSignalFeedConfig: () => fetchAPI("/api/data/signal-feed-config"),
  saveSignalFeedConfig: (config: Record<string, unknown>) =>
    fetchAPI("/api/data/signal-feed-config", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  // Briefing
  generateAfterMarketReport: () =>
    fetchAPI("/api/reports/generate-after-market", { method: "POST" }),
  generateSessionPlan: () =>
    fetchAPI("/api/reports/generate-session-plan", { method: "POST" }),
  generateBtcReport: () =>
    fetchAPI("/api/reports/generate-btc", { method: "POST" }),
  getBriefingArchive: (days = 7) =>
    fetchAPI(`/api/reports/briefing-archive?days=${days}`),

  // Bitcoin
  getBtcSnapshot: () => fetchAPI("/api/data/btc/snapshot"),
  getBtcLatestReport: () => fetchAPI("/api/reports/btc-latest"),

  // Watchlist Momentum
  getWatchlistMomentum: () => fetchAPI("/api/data/watchlist-momentum"),

  // Lernpfade Stats
  getLernpfadeStats: () => fetchAPI("/api/data/lernpfade-stats"),
};
