-- ══════════════════════════════════════════════════════════════
-- Web Intelligence Migration
-- Erstellt: 2026-03-19
-- Beschreibung: Tavily-Cache + Watchlist Prio-Feld für Web-Scans
-- ══════════════════════════════════════════════════════════════

-- ── Web Intelligence Cache ────────────────────────────────────
-- Speichert Tavily-Suchergebnisse pro Ticker mit TTL
CREATE TABLE IF NOT EXISTS web_intelligence_cache (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker        TEXT NOT NULL,
    prio          INT  NOT NULL DEFAULT 4,       -- 1=täglich 3x, 2=täglich 1x, 3=wöchentlich, 4=nur manuell
    summary       TEXT,                          -- 3-5 Stichpunkte (von DeepSeek komprimiert)
    raw_snippets  JSONB DEFAULT '[]',            -- Rohdaten von Tavily
    earnings_date DATE,                          -- Earnings-Datum zum Zeitpunkt der Suche
    searched_at   TIMESTAMP DEFAULT NOW(),
    expires_at    TIMESTAMP,                     -- searched_at + TTL je nach Prio
    UNIQUE(ticker)
);

CREATE INDEX IF NOT EXISTS idx_web_intel_ticker
    ON web_intelligence_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_web_intel_expires
    ON web_intelligence_cache(expires_at);

-- ── Watchlist: web_prio Feld hinzufügen ──────────────────────
-- NULL = automatisch aus Earnings-Abstand berechnet
-- 1-4  = manuell gesetzt, überschreibt Auto-Berechnung
ALTER TABLE watchlist
    ADD COLUMN IF NOT EXISTS web_prio INT DEFAULT NULL;

COMMENT ON COLUMN watchlist.web_prio IS
    'NULL=Auto (aus Earnings-Datum), 1=Täglich 3x, 2=Täglich 1x, 3=Wöchentlich, 4=Kein Web-Scan';

CREATE INDEX IF NOT EXISTS idx_web_intel_searched
    ON web_intelligence_cache(searched_at);
