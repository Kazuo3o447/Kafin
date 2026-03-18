const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  // Watchlist
  getWatchlist: () => fetchAPI("/api/watchlist"),
  addTicker: (data: any) => fetchAPI("/api/watchlist", { method: "POST", body: JSON.stringify(data) }),
  removeTicker: (ticker: string) => fetchAPI(`/api/watchlist/${ticker}`, { method: "DELETE" }),

  // Reports
  generateMorningBriefing: () => fetchAPI("/api/reports/generate-morning", { method: "POST" }),
  generateSundayReport: () => fetchAPI("/api/reports/generate-sunday", { method: "POST" }),
  generateAuditReport: (ticker: string) => fetchAPI(`/api/reports/generate/${ticker}`, { method: "POST" }),
  getLatestReport: () => fetchAPI("/api/reports/latest"),
  postEarningsReview: (ticker: string) => fetchAPI(`/api/reports/post-earnings-review/${ticker}`, { method: "POST" }),

  // Data
  getMacro: () => fetchAPI("/api/data/macro"),
  getMarketOverview: () => fetchAPI("/api/data/market-overview"),
  getCompanyProfile: (ticker: string) => fetchAPI(`/api/data/company/${ticker}/profile`),
  getNewsMemory: (ticker: string) => fetchAPI(`/api/news/memory/${ticker}`),
  getLongTermMemory: (ticker: string) => fetchAPI(`/api/data/long-term-memory/${ticker}`),
  getPerformance: () => fetchAPI("/api/data/performance"),

  // Actions
  runNewsScan: () => fetchAPI("/api/news/scan", { method: "POST" }),
  runSecScan: () => fetchAPI("/api/news/sec-scan", { method: "POST" }),
  runMacroScan: () => fetchAPI("/api/news/macro-scan", { method: "POST" }),
  runSignalScan: () => fetchAPI("/api/signals/scan", { method: "POST" }),
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
};
