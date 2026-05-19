from __future__ import annotations

from data.sources.intelligence_adapter import build_filter_queue_entries, infer_market_regime


def test_build_filter_queue_entries_only_keeps_relevant_watchlist_items():
    watchlist = [
        {"ticker": "NVDA", "note": "AI leader"},
        {"ticker": "MSFT", "note": "platform"},
    ]
    snapshots = {
        "NVDA": {
            "news": {"company": [{"title": "Beat and raise", "sentiment_label": "positive"}] * 3},
            "sentiment": {"company": {"label": "positive", "score": 0.42}},
        },
        "MSFT": {
            "news": {"company": []},
            "sentiment": {"company": {"label": "neutral", "score": 0.0}},
        },
    }

    entries = build_filter_queue_entries(watchlist, snapshots, {"market_regime": "risk_on"})

    assert len(entries) == 1
    assert entries[0]["ticker"] == "NVDA"
    assert entries[0]["priority"] == "high"


def test_infer_market_regime_flags_risk_off_when_vix_is_high():
    regime = infer_market_regime(
        technicals={"vix_close": 28, "spy_above_sma_200": False},
        macro={"fed_funds_rate": 5.25},
        fear_greed={"value": 30},
        market_sentiment={"score": -0.3},
    )

    assert regime == "risk_off"