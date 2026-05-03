"""
Analysis Router - KI-Analyse Endpoints

- /api/finbert/analyze: Sentiment-Analyse
- /api/signals/scan: Signal-Scan für Watchlist
- /api/opportunities/scan: Opportunity-Scanner
- /api/chart-analysis/{ticker}: Technische Chartanalyse
- /api/chart-analysis-top: Top-N Watchlist Chartanalyse
- /api/analysis/chat/{ticker}: Multi-Turn AI-Chat pro Ticker (NEU)
- /api/market-audit: Gesamtmarkt-Analyse mit DeepSeek

NEU v6.4.0: Multi-Turn AI-Chat mit kontext-basierten Antworten,
Was-wenn-Szenarien und Options-Setup-Empfehlungen.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from backend.app.logger import get_logger
from backend.app.analysis.finbert import analyze_sentiment
from backend.app.analysis.signal_scanner import scan_all_signals
from backend.app.analysis.opportunity_scanner import scan_upcoming_opportunities
from backend.app.analysis.chart_analyst import analyze_chart, analyze_top_watchlist
from backend.app.analysis.deepseek import call_deepseek, call_deepseek_chat
from backend.app.data.market_overview import (
    get_market_overview, get_market_breadth, get_intermarket_signals, get_market_news_for_sentiment
)
from backend.app.data.fred import get_macro_snapshot
from backend.app.embeddings import embed_text
from backend.app.database import get_pool

logger = get_logger(__name__)

router = APIRouter(tags=["analysis"])

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class TickerChatRequest(BaseModel):
    messages: list[ChatMessage]          # komplette Gesprächshistorie
    context_snapshot: dict               # vom Frontend mitgeschickt

@router.post("/api/finbert/analyze")
async def api_finbert_analyze(text: str):
    score = analyze_sentiment(text)
    return {"text": text, "sentiment_score": score}

@router.post("/api/signals/scan")
async def api_signal_scan():
    """Manueller Signal-Scan für alle Watchlist-Ticker."""
    logger.info("API Call: signals-scan")
    signals = await scan_all_signals()
    return {
        "status": "success",
        "signals_found": len(signals),
        "signals": signals,
    }

@router.get("/api/opportunities")
async def api_opportunities(days: int = 7):
    """Scannt nach interessanten Earnings-Setups."""
    logger.info(f"API Call: opportunities (days={days})")
    results = await scan_upcoming_opportunities(days_ahead=days)
    return {
        "status": "success",
        "count": len(results),
        "opportunities": results,
    }

@router.get("/api/chart-analysis/{ticker}")
async def api_chart_analysis(ticker: str):
    """Technische Chartanalyse mit konkreten Levels."""
    logger.info(f"API Call: chart-analysis for {ticker}")
    return await analyze_chart(ticker)

@router.get("/api/chart-analysis-top")
async def api_chart_analysis_top(limit: int = 5):
    """Chartanalyse für die Top-N Watchlist-Ticker."""
    logger.info(f"API Call: chart-analysis-top (limit={limit})")
    results = await analyze_top_watchlist(limit)
    return {"tickers": results}

@router.post("/api/analysis/chat/{ticker}")
async def api_ticker_chat(ticker: str, body: TickerChatRequest):
    """
    Multi-Turn AI-Chat für einen Ticker.
    Kontext (Scores, Metriken, letzter Report) kommt vom Frontend mit.
    Max 8 Nachrichten werden akzeptiert — ältere werden serverseitig abgeschnitten.
    """
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Ungültiger Ticker")

    ctx = body.context_snapshot
    ticker_upper = ticker.upper()

    # System-Prompt aus Kontext aufbauen
    report_excerpt = str(ctx.get("report_text", ""))[:2000]  # max 2000 Zeichen
    system_prompt = f"""Du bist ein erfahrener Trader-Assistent für die Kafin-Plattform.
Du analysierst {ticker_upper} und beantwortest Fragen dazu präzise und knapp.

AKTUELLER KONTEXT:
Ticker: {ticker_upper}
Preis: ${ctx.get('price', 'N/A')}
Opportunity-Score: {ctx.get('opportunity_score', 'N/A')}/10
Torpedo-Score: {ctx.get('torpedo_score', 'N/A')}/10
Empfehlung: {ctx.get('recommendation', 'N/A')}
ATR(14): {ctx.get('atr_14', 'N/A')}
IV ATM: {ctx.get('iv_atm', 'N/A')}%
Expected Move: ±{ctx.get('expected_move_pct', 'N/A')}%
RSI: {ctx.get('rsi', 'N/A')}
Trend: {ctx.get('trend', 'N/A')}

LETZTER AUDIT-REPORT (Auszug):
{report_excerpt if report_excerpt else 'Noch kein Report generiert.'}

REGELN:
- Antworte auf Deutsch, maximal 150 Wörter
- Keine Index-Shorts empfehlen (SH, PSQ, SQQQ, SPY-Puts auf breiten Markt)
- Bei bärischer Einschätzung: Sektor-ETF-Puts, Einzeltitel-Puts oder Pair-Trades
- Wenn Daten fehlen, klar sagen was unklar ist
- Keine Finanzberatung — Empfehlungen sind Analysen, keine Garantien"""

    # Nachrichten auf 8 begrenzen (die letzten 8)
    messages = [{"role": m.role, "content": m.content}
                for m in body.messages[-8:]]

    answer = await call_deepseek_chat(
        system_prompt=system_prompt,
        messages=messages,
        max_tokens=400,
    )

    return {"ticker": ticker_upper, "answer": answer}

@router.post("/api/market-audit")
async def api_market_audit():
    """
    DeepSeek bewertet den Gesamtmarkt und gibt eine
    konkrete Trading-Strategie-Empfehlung aus.
    """
    logger.info("API Call: market-audit")
    import asyncio

    overview, breadth, intermarket, macro, news_sentiment = await asyncio.gather(
        get_market_overview(),
        get_market_breadth(),
        get_intermarket_signals(),
        get_macro_snapshot(),
        get_market_news_for_sentiment(),
        return_exceptions=True,
    )

    def safe(r, default={}):
        return default if isinstance(r, Exception) else r

    overview = safe(overview, {})
    breadth = safe(breadth, {})
    intermarket = safe(intermarket, {})
    macro = safe(macro)
    news_sentiment = safe(news_sentiment, {})

    indices = overview.get("indices", {})
    sectors = overview.get("sector_ranking_5d", [])
    signals = intermarket.get("signals", {})

    index_lines = []
    for sym, d in indices.items():
        if isinstance(d, dict) and not d.get("error"):
            index_lines.append(
                f"{d.get('name', sym)}: ${d.get('price', '?'):.2f} "
                f"({d.get('change_1d_pct', 0):+.1f}% heute, "
                f"{d.get('change_1m_pct', 0):+.1f}% 1M) "
                f"RSI {d.get('rsi_14', '?')} Trend: {d.get('trend', '?')}"
            )

    sector_lines = [
        f"{s['name']}: {s['perf_5d']:+.1f}%"
        for s in sectors[:11]
    ]

    breadth_text = (
        f"Marktbreite (30-Titel-Sample): "
        f"{breadth.get('pct_above_sma50', '?')}% über SMA50, "
        f"{breadth.get('pct_above_sma200', '?')}% über SMA200 | "
        f"Signal: {breadth.get('breadth_signal', '?').upper()} | "
        f"Advancing: {breadth.get('advancing', '?')}, "
        f"Declining: {breadth.get('declining', '?')}"
    )

    signal_lines = []
    for k, v in signals.items():
        if not k.endswith("_note"):
            note = signals.get(f"{k}_note", "")
            signal_lines.append(f"{k}: {v}" + (f" — {note}" if note else ""))

    energy_stress = signals.get("energy_stress", "neutral")
    energy_note = signals.get("energy_note", "")
    stagflation = signals.get("stagflation_warning", False)
    stagflation_note = signals.get("stagflation_note", "")

    energy_block = f"""ENERGIE-SIGNAL: {energy_stress.upper()}
{energy_note}"""

    if stagflation:
        energy_block += f"""

⚡ STAGFLATIONS-WARNUNG AKTIV:
{stagflation_note}
Konsequenz: Fed kann trotz Schwäche nicht senken.
Wachstumstitel unter doppeltem Druck (Bewertung + Zinsen)."""

    cat_sent = news_sentiment.get("category_sentiment", {})
    news_lines = []
    for cat, sent in cat_sent.items():
        label = sent.get("label", "neutral")
        score = sent.get("score", 0.0)
        count = sent.get("count", 0)
        cat_label = {
            "fed_rates": "Fed/Zinsen",
            "macro_data": "Makro-Daten",
            "geopolitics": "Geopolitik",
            "market_general": "Allgemein",
        }.get(cat, cat)
        news_lines.append(
            f"{cat_label}: {label} ({score:+.2f}, {count} Artikel)"
        )

    top_headlines = news_sentiment.get("headlines", [])[:5]
    headline_lines = []
    for h in top_headlines:
        score = h.get("sentiment_score", 0.0)
        headline_lines.append(
            f"  [{score:+.2f}] {h.get('headline', '')} "
            f"({h.get('source', '')})"
        )

    macro_text = (
        f"Fed Rate: {getattr(macro, 'fed_rate', '?')}% | "
        f"VIX: {getattr(macro, 'vix', '?')} | "
        f"Credit Spread (HY): {getattr(macro, 'credit_spread_bps', '?')} | "
        f"Yield Curve (10Y-2Y): {getattr(macro, 'yield_curve_10y_2y', '?')} | "
        f"Regime: {getattr(macro, 'regime', '?')}"
    ) if macro else "Makro-Daten nicht verfügbar"

    system_prompt = (
        "Du bist ein erfahrener Senior-Marktanalyst bei einem Hedge Fund. "
        "Du analysierst das aktuelle Marktregime und gibst dem Trader "
        "eine konkrete, meinungsstarke Handlungsempfehlung auf Deutsch. "
        "Keine Floskeln. Direkt. Maximal 25 Zeilen."
    )

    prompt = f"""Analysiere das aktuelle Marktumfeld und gib dem Trader eine klare Handlungsempfehlung. Antworte auf Deutsch.
Maximal 25 Zeilen. Direkt, meinungsstark, kein Hedging.

ABSOLUTE REGEL: Empfiehle NIEMALS breite Index-Shorts (SH, PSQ, SQQQ).
Nur: Sektor-ETF-Puts, Einzeltitel-Puts, Pair-Trades, Cash-Position erhöhen.

MARKTDATEN:

INDIZES:
{chr(10).join(index_lines)}

SEKTOREN (5-Tage-Performance, stärkste zuerst):
{chr(10).join(sector_lines)}

MARKTBREITE:
{breadth_text}

CROSS-ASSET SIGNALE:
{chr(10).join(signal_lines) if signal_lines else "Keine Signale berechnet"}

MAKRO:
{macro_text}

ENERGIE & ROHSTOFFE:
{energy_block}

ROTATIONS-MUSTER:
{overview.get('rotation_story', 'Kein klares Rotationsmuster')}
Defensiv (XLU/XLV/XLP) Ø {overview.get('defensive_avg_5d', 0):+.1f}%
vs. Offensiv (XLK/XLC/XLY) Ø {overview.get('offensive_avg_5d', 0):+.1f}%

NEWS-SENTIMENT (FinBERT, letzte 24h):
{chr(10).join(news_lines) if news_lines else "Keine News-Daten"}

TOP SCHLAGZEILEN (stärkstes Sentiment):
{chr(10).join(headline_lines) if headline_lines else "Keine Headlines"}

DEINE AUFGABE:
1. REGIME: Welches Marktregime herrscht gerade? (Risk-On / Mixed / Risk-Off)
   Begründe mit konkreten Zahlen.
2. MARKTGESUNDHEIT: Ist die Stärke/Schwäche breit oder konzentriert?
   Was sagt die Marktbreite?
3. SEKTORROTATION: Wohin fließt das Geld? Was bedeutet das?
4. DIVERGENZEN: Gibt es Widersprüche zwischen den Signalen?
   (z.B. Aktien steigen aber Credit Spreads weiten sich)
5. KONKRETE EMPFEHLUNG: Was bedeutet dieses Umfeld für einen
   Earnings-Trader mit Einzelaktien-Fokus?
   - Beta erhöhen oder reduzieren?
   - Welche Sektoren meiden, welche bevorzugen?
   - Ist jetzt ein guter Zeitpunkt für neue Positionen?
6. ENERGIE & GEOPOLITIK: Wenn Energie-Schock aktiv:
   Erkläre die Transmission (Öl → Inflation → Fed →
   Zinsen → Markt). Welche Sektoren leiden,
   welche profitieren? Was bedeutet das für
   einen Earnings-Trader der nächste Woche
   Quartalszahlen erwartet?"""

    try:
        report = await call_deepseek(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=1500,
        )
        return {
            "status": "success",
            "report": report,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_used": {
                "indices": len(index_lines),
                "sectors": len(sector_lines),
                "breadth": breadth.get("breadth_signal"),
                "regime": getattr(macro, "regime", None),
            }
        }
    except Exception as e:
        logger.error(f"Market Audit Fehler: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/api/data/rag/similar-news")
async def api_rag_similar_news(
    query: str = Query(..., min_length=5),
    ticker: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20),
):
    """Semantische Suche in News-Stichpunkten."""
    vec = await embed_text(query)
    if vec is None:
        return {"results": [], "error": "Embedding-Modell nicht verfügbar"}

    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    pool = await get_pool()
    async with pool.acquire() as conn:
        if ticker:
            rows = await conn.fetch(
                """
                SELECT ticker, date, bullet_points,
                  sentiment_score, category,
                  1 - (embedding <=> $1::vector) AS similarity
                FROM short_term_memory
                WHERE embedding IS NOT NULL
                  AND ticker = $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                vec_str, ticker.upper(), limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT ticker, date, bullet_points,
                  sentiment_score, category,
                  1 - (embedding <=> $1::vector) AS similarity
                FROM short_term_memory
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                vec_str, limit,
            )

    results = []
    for row in rows:
        results.append({
            "ticker":          row["ticker"],
            "date":            row["date"].isoformat() if row["date"] else None,
            "bullet_points":   row["bullet_points"],
            "sentiment_score": row["sentiment_score"],
            "category":        row["category"],
            "similarity":      round(float(row["similarity"]), 3),
        })

    return {
        "query":   query,
        "results": results,
        "count":   len(results),
    }

@router.get("/api/data/rag/similar-audits")
async def api_rag_similar_audits(
    query: str = Query(..., min_length=5),
    limit: int = Query(3, ge=1, le=10),
):
    """Findet historische Audit-Reports ähnlich zur Anfrage."""
    vec = await embed_text(query)
    if vec is None:
        return {"results": [], "error": "Kein Embedding"}

    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ticker, report_date,
              recommendation, opportunity_score,
              torpedo_score,
              LEFT(report_text, 300) AS preview,
              1 - (embedding <=> $1::vector) AS similarity
            FROM audit_reports
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vec_str, limit,
        )

    return {
        "query":   query,
        "results": [dict(r) for r in rows],
    }
