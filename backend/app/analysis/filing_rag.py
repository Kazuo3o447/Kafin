"""
10-Q Tonalitäts-Diff.
Extrahiert nur relevante Abschnitte (~40-80K Tokens)
und analysiert mit DeepSeek Chat (128K Kontext).
Fallback auf Kimi K2.5 (256K) wenn größer.

Kein Gemini nötig. Keine neuen API-Keys.
Kosten: ~$0.003 pro Analyse.
"""
import asyncio
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

MAX_SECTION_CHARS = 25_000   # Pro Abschnitt
DEEPSEEK_LIMIT   = 80_000    # Zeichen → ~25K Tokens
KIMI_LIMIT       = 200_000   # Zeichen → ~65K Tokens


DIFF_PROMPT = """Du bist ein erfahrener Buy-Side-Analyst.
Vergleiche die Management-Tonalität zwischen zwei
Quartalsberichten (10-Q) von {ticker}.

AKTUELLES QUARTAL ({current_period}):
{current_text}

VORHERIGES QUARTAL ({prev_period}):
{prev_text}

Aufgabe: Finde wo Management die Sprache
bei diesen Themen verändert hat:
• Margen und Kosten
• Umsatz und Wachstum
• Risikofaktoren
• Guidance und Ausblick
• Liquidität und Verschuldung

Format (exakt einhalten):

## [THEMA]
VORHER: "Originalformulierung aus älterem Bericht"
JETZT:  "Geänderte Formulierung aus neuerem Bericht"
→ Was das bedeutet: 1-2 Sätze konkrete Einschätzung.
Signal: POSITIV / NEGATIV / NEUTRAL

Wenn keine Änderung: ## [THEMA] — Signal: NEUTRAL

Am Ende:
## GESAMT
Signal: BULLISH / BEARISH / GEMISCHT / NEUTRAL
Fazit: 2-3 Sätze für den Trader.

Antworte auf Deutsch. Sei direkt und handelsorientiert.
Keine Floskeln."""


async def _choose_model(text_chars: int) -> str:
    """
    Wählt das beste Modell basierend auf Textmenge.
    Alles bleibt in den bestehenden Integrationen.
    """
    if text_chars <= DEEPSEEK_LIMIT:
        return "deepseek-chat"
    elif text_chars <= KIMI_LIMIT:
        return "kimi"
    else:
        # Zu lang — Abschnitte werden intern gecroppt
        return "deepseek-chat"


async def _call_model(
    model: str,
    system: str,
    prompt: str,
) -> str | None:
    """Ruft das gewählte Modell auf."""
    if model == "deepseek-chat":
        from backend.app.analysis.deepseek import (
            call_deepseek,
        )
        result = await call_deepseek(
            system,
            prompt,
            model="deepseek-chat",
            max_tokens=3000,
            temperature=0.1,
        )
        return result or None

    elif model == "kimi":
        from backend.app.config import settings
        if not settings.kimi_api_key:
            # Kimi nicht konfiguriert → DeepSeek Fallback
            logger.info(
                "Kimi nicht konfiguriert → "
                "DeepSeek Fallback"
            )
            from backend.app.analysis.deepseek import (
                call_deepseek,
            )
            return await call_deepseek(
                system,
                prompt[:100_000],  # Crop für DeepSeek
                model="deepseek-chat",
                max_tokens=3000,
                temperature=0.1,
            )

        from backend.app.analysis.kimi import call_kimi
        result = await call_kimi(
            system, prompt, max_tokens=3000
        )
        return result or None

    return None


async def get_filing_diff(
    ticker: str,
    filing_type: str = "10-Q",
) -> dict:
    """
    Vergleicht letzte zwei 10-Q Berichte.
    Nutzt smarte Sektion-Extraktion + DeepSeek Chat.
    Kein Gemini, kein neuer API-Key.
    """
    cache_key = (
        f"filing_diff:{ticker.upper()}:{filing_type}"
    )
    cached = cache_get(cache_key)
    if cached:
        return cached

    from backend.app.data.sec_edgar import (
        get_10q_sections,
    )

    logger.info(
        f"10-Q Diff für {ticker}: "
        f"Lade Abschnitte von SEC EDGAR..."
    )

    # Beide Quartale parallel laden
    current, previous = await asyncio.gather(
        get_10q_sections(ticker, index=0),
        get_10q_sections(ticker, index=1),
        return_exceptions=True,
    )

    if isinstance(current, Exception) or not current:
        return {
            "ticker":    ticker.upper(),
            "available": False,
            "error": (
                f"Aktuelles {filing_type} nicht "
                f"geladen. SEC EDGAR antwortet "
                f"möglicherweise nicht."
            ),
        }

    if isinstance(previous, Exception) or not previous:
        return {
            "ticker":    ticker.upper(),
            "available": False,
            "error": (
                f"Vorheriges {filing_type} nicht "
                f"gefunden. Vergleich nicht möglich."
            ),
        }

    # Relevante Abschnitte zusammenführen
    def _build_section_text(filing: dict) -> str:
        secs = filing.get("sections", {})
        parts = []
        if secs.get("mda"):
            parts.append(
                "=== MANAGEMENT DISCUSSION ===\n"
                + secs["mda"][:MAX_SECTION_CHARS]
            )
        if secs.get("risk_factors"):
            parts.append(
                "=== RISIKOFAKTOREN ===\n"
                + secs["risk_factors"][:MAX_SECTION_CHARS]
            )
        if secs.get("outlook"):
            parts.append(
                "=== AUSBLICK / GUIDANCE ===\n"
                + secs["outlook"][:MAX_SECTION_CHARS]
            )
        return "\n\n".join(parts)

    current_text  = _build_section_text(current)
    previous_text = _build_section_text(previous)

    if not current_text.strip():
        return {
            "ticker":    ticker.upper(),
            "available": False,
            "error": (
                "Keine relevanten Abschnitte "
                "im 10-Q gefunden (MD&A, Risiken, "
                "Ausblick). Filing-Format unbekannt."
            ),
        }

    total_chars = len(current_text) + len(previous_text)
    model       = await _choose_model(total_chars)

    logger.info(
        f"10-Q Diff {ticker}: "
        f"{total_chars} Zeichen → Modell: {model}"
    )

    prompt = DIFF_PROMPT.format(
        ticker=ticker.upper(),
        current_period=current.get("period", "Aktuell"),
        prev_period=previous.get("period", "Vorquartal"),
        current_text=current_text,
        prev_text=previous_text,
    )

    system = (
        "Du bist ein präziser Finanzanalyst. "
        "Antworte auf Deutsch. "
        "Fokussiere auf handelbare Erkenntnisse. "
        "Keine Einleitungen, keine Floskeln."
    )

    result_text = await _call_model(
        model, system, prompt
    )

    if not result_text:
        return {
            "ticker":    ticker.upper(),
            "available": False,
            "error": (
                f"Modell ({model}) konnte den "
                f"Diff nicht erstellen."
            ),
        }

    # Gesamt-Signal extrahieren
    overall = "NEUTRAL"
    upper   = result_text.upper()
    if "GESAMT" in upper:
        gesamt_idx = upper.rfind("GESAMT")
        snippet    = upper[gesamt_idx:gesamt_idx+200]
        if "BULLISH" in snippet:
            overall = "BULLISH"
        elif "BEARISH" in snippet:
            overall = "BEARISH"
        elif "GEMISCHT" in snippet:
            overall = "GEMISCHT"

    result = {
        "ticker":         ticker.upper(),
        "available":      True,
        "filing_type":    filing_type,
        "current_period": current.get("period"),
        "prev_period":    previous.get("period"),
        "overall_signal": overall,
        "diff_text":      result_text,
        "model_used":     model,
        "chars_analyzed": total_chars,
    }

    cache_set(cache_key, result, ttl_seconds=86400)
    return result
