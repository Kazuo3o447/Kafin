from __future__ import annotations

from pipeline.gates.risk_engine import RiskEngine
from pipeline.gates.screener import TradeScreener


def test_screener_blocks_penny_stock():
    report = TradeScreener().run(
        card={"handoff_to_trade_engine": True},
        snapshot={
            "metrics": {
                "average_daily_dollar_volume_30d": 10_000_000,
                "bid_ask_spread_pct": 0.1,
                "market_cap_usd": 1_000_000_000,
                "price": 4,
                "sma_200_trending_up": True,
                "days_since_52w_high": 10,
                "trading_days_to_earnings": 20,
                "instrument_type": "equity",
            }
        },
        market_regime="risk_on",
    )

    assert not report.passed
    assert "price" in report.fail_reasons


def test_risk_engine_blocks_loose_stop():
    report = RiskEngine().run(
        {
            "metrics": {
                "paper_account_value_eur": 10_000,
                "risk_per_trade_pct": 0.25,
                "entry_price": 100,
                "atr_14": 2,
                "proposed_stop_price": 90,
            }
        }
    )

    assert report.status == "risk_blocked"
    assert "stop_looser_than_atr_rule" in report.fail_reasons
