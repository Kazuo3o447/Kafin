-- Migration: Narrative Shift Tracking für short_term_memory
-- Datum: 2026-03-18
-- Beschreibung: Fügt Spalten für Narrative Intelligence hinzu

ALTER TABLE short_term_memory 
ADD COLUMN IF NOT EXISTS url TEXT,
ADD COLUMN IF NOT EXISTS is_narrative_shift BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS shift_type TEXT,
ADD COLUMN IF NOT EXISTS shift_confidence FLOAT,
ADD COLUMN IF NOT EXISTS shift_reasoning TEXT;

-- Index für schnellere Abfragen nach Narrative Shifts
CREATE INDEX IF NOT EXISTS idx_stm_narrative_shift ON short_term_memory(ticker, is_narrative_shift) WHERE is_narrative_shift = true;
