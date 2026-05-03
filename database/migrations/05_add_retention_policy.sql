-- Retention Policy für short_term_memory
-- Löscht alte Daten automatisch und optimiert Speicherplatz

-- 1. Index für effiziente Löschung nach Datum
CREATE INDEX IF NOT EXISTS idx_stm_created_at 
ON short_term_memory(created_at);

-- 2. Funktion für automatischen Cleanup
CREATE OR REPLACE FUNCTION cleanup_old_sentiment_data()
RETURNS void AS $$
BEGIN
    -- Lösche Einträge älter als 30 Tage (behält nur aktuelle Daten)
    DELETE FROM short_term_memory 
    WHERE created_at < NOW() - INTERVAL '30 days';
    
    -- Optional: Behalte wichtige Material-Events länger (90 Tage)
    -- DELETE FROM short_term_memory 
    -- WHERE created_at < NOW() - INTERVAL '90 days'
    -- AND is_material = false;
    
    RAISE NOTICE 'Cleanup completed: Removed old sentiment data';
END;
$$ LANGUAGE plpgsql;

-- 3. Automatisierten Cleanup-Job (pg_cron benötigt)
-- SELECT cron.schedule('cleanup-sentiment', '0 2 * * *', 'SELECT cleanup_old_sentiment_data();');

-- 4. Manuelle Cleanup-Funktion für Admin
CREATE OR REPLACE FUNCTION admin_cleanup_sentiment_data(days_to_keep INTEGER DEFAULT 30)
RETURNS TABLE(deleted_count INTEGER) AS $$
DECLARE
    deleted INTEGER;
BEGIN
    DELETE FROM short_term_memory 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted = ROW_COUNT;
    
    RETURN QUERY SELECT deleted;
END;
$$ LANGUAGE plpgsql;

-- 5. Speicherplatz-Optimierung
CREATE OR REPLACE FUNCTION optimize_sentiment_storage()
RETURNS void AS $$
BEGIN
    -- VACUUM für Speicherplatz-Freigabe
    EXECUTE 'VACUUM ANALYZE short_term_memory';
    
    -- Index-Neuaufbau für Performance
    EXECUTE 'REINDEX INDEX idx_stm_embedding';
    EXECUTE 'REINDEX INDEX idx_stm_ticker_quarter';
    EXECUTE 'REINDEX INDEX idx_stm_created_at';
    
    RAISE NOTICE 'Storage optimization completed';
END;
$$ LANGUAGE plpgsql;

-- 6. Monitoring-Funktion
CREATE OR REPLACE FUNCTION get_sentiment_storage_stats()
RETURNS TABLE(
    total_records BIGINT,
    table_size TEXT,
    avg_record_size_kb NUMERIC,
    oldest_record TIMESTAMP,
    newest_record TIMESTAMP,
    material_events_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_records,
        pg_size_pretty(pg_total_relation_size('short_term_memory')) as table_size,
        ROUND(
            pg_total_relation_size('short_term_memory')::NUMERIC / NULLIF(COUNT(*), 0) / 1024, 2
        ) as avg_record_size_kb,
        MIN(created_at) as oldest_record,
        MAX(created_at) as newest_record,
        COUNT(*) FILTER (WHERE is_material = true) as material_events_count
    FROM short_term_memory;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_sentiment_data() IS 'Automatischer Cleanup für alte Sentiment-Daten';
COMMENT ON FUNCTION admin_cleanup_sentiment_data(INTEGER) IS 'Manueller Admin-Cleanup mit konfigurierbarer Retention';
COMMENT ON FUNCTION optimize_sentiment_storage() IS 'Speicherplatz-Optimierung für short_term_memory';
COMMENT ON FUNCTION get_sentiment_storage_stats() IS 'Monitoring-Statistiken für Sentiment-Speicher';
