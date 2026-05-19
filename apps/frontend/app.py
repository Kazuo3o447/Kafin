from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from pipeline.audit import load_audit_events
from pipeline.config import PlatformConfig
from pipeline.graph import run_pipeline


ROOT = Path(".")
CARDS_DIR = ROOT / "research" / "cards"
LESSONS_DIR = ROOT / "research" / "lessons"
JOURNAL_DIR = ROOT / "journal"
AUDIT_DIR = ROOT / "audit"
SNAPSHOTS_DIR = ROOT / "data" / "snapshots"
WATCHLIST_PATH = ROOT / "research" / "watchlist.json"
FILTER_QUEUE_PATH = ROOT / "research" / "filter_queue.json"
MARKET_SNAPSHOT_PATH = SNAPSHOTS_DIR / "_MARKET.json"
APP_LOG_DIR = ROOT / "logs" / "frontend"

PAGES = ["Ops Desk", "Full Audit", "Watchlist", "Audit Terminal", "App Logs", "Approval Queue", "Knowledge Base", "Admin"]
LOG_LEVELS = ["debug", "info", "warning", "error"]
APP_LOG_LIMIT = 100
SENSITIVE_KEY_PARTS = ("api_key", "authorization", "cookie", "password", "secret", "token")

DEFAULT_UNIVERSE = ["NVDA", "PLTR", "ASML", "MSFT", "NET"]
COMPANY_ALIASES = {
    "NVIDIA": "NVDA",
    "NVIDIA CORP": "NVDA",
    "MICROSOFT": "MSFT",
    "MICROSOFT CORP": "MSFT",
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "AMAZON": "AMZN",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "META": "META",
    "TESLA": "TSLA",
    "PALANTIR": "PLTR",
    "CLOUDFLARE": "NET",
    "AMD": "AMD",
}

RESEARCH_METRIC_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Growth": [
        ("Revenue 5y", "revenue_5y", "number"),
        ("Revenue growth 5y", "revenue_growth_5y", "percent"),
        ("Revenue CAGR 3y", "revenue_cagr_3y", "percent"),
        ("ARR growth", "arr_growth", "percent"),
        ("NRR", "nrr", "percent"),
        ("Customer growth", "customer_growth", "percent"),
    ],
    "Margins": [
        ("Gross margin 5y", "gross_margin_5y", "percent"),
        ("Operating margin 5y", "operating_margin_5y", "percent"),
        ("FCF margin 5y", "fcf_margin_5y", "percent"),
        ("Rule of 40", "rule_of_40", "percent"),
        ("Rule of X", "rule_of_x", "number"),
        ("Rule of 20", "rule_of_20", "number"),
    ],
    "Quality": [
        ("ROIC", "roic", "percent"),
        ("ROE", "roe", "percent"),
        ("Gross profit/assets", "gross_profit_to_assets", "percent"),
        ("Net debt/EBITDA", "net_debt_to_ebitda", "multiple"),
        ("Beta", "beta", "number"),
        ("Moat rating", "moat_rating", "text"),
    ],
    "Valuation": [
        ("Forward P/E", "forward_pe", "multiple"),
        ("EV/Sales", "ev_to_sales", "multiple"),
        ("EV/Gross Profit", "ev_to_gross_profit", "multiple"),
        ("EV/FCF", "ev_to_fcf", "multiple"),
        ("PEG ratio", "peg", "multiple"),
        ("NTM P/E vs 5y median", "ntm_pe_vs_5y_median", "percent"),
    ],
    "Dilution": [
        ("Share count trend 3y", "share_count_trend_3y", "percent"),
        ("Share count growth YoY", "share_count_growth_yoy", "percent"),
        ("SBC/revenue", "sbc_to_revenue", "percent"),
        ("SBC/OCF", "sbc_to_ocf", "percent"),
        ("Net repurchase yield", "net_repurchase_yield", "percent"),
        ("FCF/share growth", "fcf_per_share_growth", "percent"),
    ],
    "Trading Gate": [
        ("Price", "price", "currency"),
        ("Market cap", "market_cap_usd", "large_currency"),
        ("Dollar volume 30d", "average_daily_dollar_volume_30d", "large_currency"),
        ("Bid-ask spread", "bid_ask_spread_pct", "percent"),
        ("52w high", "week_52_high", "currency"),
        ("Days since 52w high", "days_since_52w_high", "number"),
        ("SMA 50", "sma_50", "currency"),
        ("SMA 200", "sma_200", "currency"),
        ("ATR 14", "atr_14", "currency"),
        ("RSI 14", "rsi_14", "number"),
        ("Next earnings", "next_earnings_date", "text"),
        ("Trading days to earnings", "trading_days_to_earnings", "number"),
    ],
}

TRADER_CHART_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Growth/Margin": [
        ("Revenue growth", "revenue_growth_5y", "percent"),
        ("Gross margin", "gross_margin_5y", "percent"),
        ("Operating margin", "operating_margin_5y", "percent"),
        ("FCF margin", "fcf_margin_5y", "percent"),
        ("Rule of 40", "rule_of_40", "percent"),
    ],
    "Valuation": [
        ("Forward P/E", "forward_pe", "multiple"),
        ("EV/Sales", "ev_to_sales", "multiple"),
        ("EV/GP", "ev_to_gross_profit", "multiple"),
        ("EV/FCF", "ev_to_fcf", "multiple"),
        ("PEG", "peg", "multiple"),
    ],
    "Quality/Risk": [
        ("ROIC", "roic", "percent"),
        ("Net debt/EBITDA", "net_debt_to_ebitda", "multiple"),
        ("SBC/revenue", "sbc_to_revenue", "percent"),
        ("Share count 3y", "share_count_trend_3y", "percent"),
        ("Bid/ask spread", "bid_ask_spread_pct", "percent"),
    ],
}

SCORE_BLOCKS = [
    ("A", "Wachstum und Marktchance", "growth_market", 18),
    ("B", "Unit Economics und Margen", "unit_economics_margins", 14),
    ("C", "Qualitaet und Moat", "quality_moat", 18),
    ("D", "Bewertung relativ zu Wachstum", "valuation", 14),
    ("E", "Kapitaldisziplin und Verwaesserung", "capital_discipline_dilution", 12),
    ("F", "Katalysatoren, Revisionen und Sentiment", "catalysts_revisions_sentiment", 12),
    ("G", "Risiko und Fragilitaet", "risk_fragility", 12),
]


st.set_page_config(page_title="Kafin Research Terminal", page_icon=None, layout="wide")


def main() -> None:
    ensure_session()
    page = "unknown"
    app_log("debug", "app", "render_start", {"session_id": st.session_state["session_id"]})
    try:
        inject_css()
        page = render_sidebar()
        st.session_state["active_page"] = page
        app_log("info", "navigation", "page_selected", {"page": page})

        if page == "Ops Desk":
            render_ops_desk()
        elif page == "Full Audit":
            render_full_audit()
        elif page == "Watchlist":
            render_watchlist_page()
        elif page == "Audit Terminal":
            render_audit_terminal()
        elif page == "App Logs":
            render_app_logs_page()
        elif page == "Approval Queue":
            render_approval_queue()
        elif page == "Knowledge Base":
            render_knowledge_base()
        elif page == "Admin":
            render_admin()

        if page != "App Logs":
            render_app_log_drawer()
        app_log("debug", "app", "render_complete", {"page": page})
    except Exception as exc:
        app_log("error", "app", "unhandled_exception", {"page": page}, exc=exc)
        render_fatal_error(exc)
        render_app_log_drawer(force_open=True)


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="brand">
              <div class="brand-mark">KR</div>
              <div>
                <div class="brand-title">Kafin Research</div>
                <div class="brand-subtitle">local-first agent terminal</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        page = st.radio("Navigation", PAGES, label_visibility="collapsed")
        st.markdown('<div class="sidebar-rule"></div>', unsafe_allow_html=True)
        st.markdown("**System Snapshot**")
        sidebar_metric("Cards", len(load_card_index()))
        sidebar_metric("Audit runs", len(load_run_index()))
        sidebar_metric("Snapshots", len(list(SNAPSHOTS_DIR.glob("*.json"))))
        sidebar_metric("Lessons", count_lesson_files())
        st.markdown('<div class="sidebar-rule"></div>', unsafe_allow_html=True)
        st.caption("Guardrails")
        st.markdown(
            """
            <div class="mini-log">
              <div><span class="dot green"></span>No broker API</div>
              <div><span class="dot green"></span>No autonomous orders</div>
              <div><span class="dot yellow"></span>Phase-gated pipeline</div>
              <div><span class="dot yellow"></span>Human decision required</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sidebar-rule"></div>', unsafe_allow_html=True)
        st.toggle("App log", value=False, key="show_app_log", help="Lokales Frontend-Log unten anzeigen")
        return page


def render_ops_desk() -> None:
    app_log("debug", "page", "render_ops_desk")
    cards = load_card_index()
    runs = load_run_index()
    snapshots = sorted(SNAPSHOTS_DIR.glob("*.json"))
    latest_run = runs[0] if runs else None
    universe = build_company_universe(cards)

    render_title(
        "Research Cockpit",
        "Freie Unternehmenssuche, DeepSeek-Research, Kennzahlenwand, Scores, Risiken und Trading-Kontext.",
    )
    selected_ticker = render_company_search_bar(universe, cards)
    selected_payload = payload_for_ticker(selected_ticker, cards)
    selected_snapshot = snapshot_for_ticker(selected_ticker)
    selected_metrics = metrics_for_company(selected_ticker, selected_payload, selected_snapshot)
    completeness = research_metric_completeness(selected_metrics)
    render_data_availability_notice(selected_ticker, selected_payload, selected_snapshot)
    source_count = len(selected_payload.get("source_list", [])) if selected_payload else len(selected_snapshot.get("sources", []))
    news_count = len(selected_payload.get("news_digest", [])) if selected_payload else len(selected_snapshot.get("news", {}).get("company", []))

    metric_row(
        [
            ("Ticker", selected_ticker, company_short_name(selected_ticker, cards)),
            ("Score", str(selected_payload.get("growth_research_score", "unknown")), selected_payload.get("gate", "no card")),
            ("Research Data", f"{completeness['filled']}/{completeness['total']}", f"{completeness['pct']}% filled"),
            ("Quellen", str(source_count), f"{news_count} news"),
            ("Snapshots", str(len(snapshots)), "local files"),
            ("Audit Runs", str(len(runs)), "event streams"),
        ]
    )

    render_research_action_bar(selected_ticker)

    main_col, side_col = st.columns([2.25, 0.95], gap="medium")
    with main_col:
        render_trader_overview_panel(selected_ticker, selected_payload, selected_snapshot, selected_metrics)
        render_metric_chart_panel(selected_metrics)
        render_research_metrics_panel(selected_ticker, selected_payload, selected_snapshot, selected_metrics)
        render_research_score_panel(selected_payload)
        render_all_available_metrics_panel(selected_metrics, selected_payload, selected_snapshot)
    with side_col:
        render_company_status_panel(selected_ticker, selected_payload, selected_snapshot, completeness)
        render_run_console(selected_ticker)
        render_sentiment_news_panel(selected_payload, selected_snapshot)
        render_risk_register_panel(selected_payload)
        render_gate_matrix_for_company(selected_payload)
        render_latest_audit(latest_run)

    render_bottom_command_strip()


def render_run_console(selected_ticker: str) -> None:
    with panel("Research Run", "Phase 1 erzeugt Card, Red-Team, Screener und DeepSeek-Audit, falls API aktiv ist."):
        ticker = st.text_input("Run ticker", selected_ticker, label_visibility="collapsed").upper().strip()
        phase = st.select_slider("Phase", options=[0, 1, 2, 3, 4], value=1)
        force_llm = st.toggle("DeepSeek erlauben", value=True, key=f"run_llm_{selected_ticker}")
        run_col, replay_col = st.columns([1.2, 0.8], gap="small")
        run_clicked = run_col.button("Research starten", use_container_width=True, type="primary")
        replay_clicked = replay_col.button("Refresh desk", use_container_width=True)
        if run_clicked:
            if not ticker:
                app_log("warning", "run_console", "run_rejected", {"reason": "ticker_missing"})
                st.error("Ticker required.")
            else:
                app_log("info", "run_console", "pipeline_run_requested", {"ticker": ticker, "phase": phase, "allow_llm": force_llm})
                if int(phase) >= 1:
                    ensure_snapshot_for_research(ticker)
                config = PlatformConfig.from_env(phase=int(phase))
                if force_llm:
                    config = PlatformConfig(
                        project_root=config.project_root,
                        phase=config.phase,
                        audit_dir=config.audit_dir,
                        snapshots_dir=config.snapshots_dir,
                        cards_dir=config.cards_dir,
                        evidence_dir=config.evidence_dir,
                        rejected_dir=config.rejected_dir,
                        journal_dir=config.journal_dir,
                        allow_llm=True,
                    )
                try:
                    state = run_pipeline(ticker, config=config)
                except Exception as exc:
                    app_log("error", "run_console", "pipeline_run_failed", {"ticker": ticker, "phase": phase}, exc=exc)
                    raise
                app_log(
                    "info",
                    "run_console",
                    "pipeline_run_completed",
                    {"ticker": ticker, "phase": phase, "run_id": state["run_id"], "status": state["status"]},
                )
                st.session_state["last_run_state"] = state
                st.success(f"Run {state['run_id']} -> {state['status']}")
                st.rerun()
        if replay_clicked:
            app_log("debug", "run_console", "manual_refresh_requested")
            st.rerun()
        state = st.session_state.get("last_run_state")
        if state:
            render_code_block(json.dumps(compact_state(state), indent=2), language="json", height=260)
        else:
            render_terminal_lines(
                [
                    f"$ python -m pipeline.run {selected_ticker} --phase 1",
                    "Research Card + Red-Team + Screener",
                    "DeepSeek: controlled by toggle and .env",
                ],
                height=120,
            )


def render_watchlist_panel(selected_ticker: str) -> None:
    with panel("Watchlist", "Compact operator list. No trade command."):
        watchlist = read_json(WATCHLIST_PATH, default=[])
        in_watchlist = any(item.get("ticker") == selected_ticker for item in watchlist)
        add_col, input_col = st.columns([0.82, 1.18], gap="small")
        if add_col.button(
            "Add selected",
            use_container_width=True,
            disabled=in_watchlist or selected_ticker == "UNKNOWN",
        ):
            watchlist.append({"ticker": selected_ticker, "note": "selected in research desk"})
            write_json(WATCHLIST_PATH, watchlist)
            app_log("info", "watchlist", "selected_ticker_added", {"ticker": selected_ticker})
            st.rerun()
        new_ticker = input_col.text_input("Manual ticker", placeholder="MSFT", label_visibility="collapsed").upper().strip()
        if st.button("Add manual ticker", use_container_width=True):
            if new_ticker and not any(item.get("ticker") == new_ticker for item in watchlist):
                watchlist.append({"ticker": new_ticker, "note": ""})
                write_json(WATCHLIST_PATH, watchlist)
                app_log("info", "watchlist", "ticker_added", {"ticker": new_ticker})
                st.rerun()
            elif not new_ticker:
                app_log("warning", "watchlist", "ticker_add_rejected", {"reason": "ticker_missing"})
            else:
                app_log("debug", "watchlist", "ticker_add_skipped", {"ticker": new_ticker, "reason": "duplicate"})
        if watchlist:
            compact_rows = [{"ticker": item.get("ticker", "-"), "note": item.get("note", "")} for item in watchlist[-6:]]
            st.dataframe(compact_rows, use_container_width=True, hide_index=True, height=142)
        else:
            render_empty("No watchlist entries.", ["select company", "add selected"])


def render_watchlist_page() -> None:
    app_log("debug", "page", "render_watchlist_page")
    render_title("Watchlist", "Separate Beobachtungsliste fuer Ideen, Filter Queue und Marktueberblick. Research bleibt unabhaengig.")

    watchlist = read_json(WATCHLIST_PATH, default=[])
    cards = load_card_index()
    add_col, remove_col, note_col = st.columns([0.8, 0.8, 1.4], gap="small")
    new_ticker = add_col.text_input("Ticker hinzufuegen", placeholder="MSFT").upper().strip()
    remove_options = ["-"] + [str(item.get("ticker", "")).upper() for item in watchlist if item.get("ticker")]
    remove_ticker = remove_col.selectbox("Entfernen", remove_options)
    note = note_col.text_input("Notiz", placeholder="Warum beobachten?")

    action_add, action_remove, action_refresh = st.columns([0.55, 0.55, 1.9], gap="small")
    if action_add.button("Hinzufuegen", use_container_width=True, type="primary"):
        if new_ticker and new_ticker not in watchlist_tickers():
            watchlist.append({"ticker": new_ticker, "note": note})
            write_json(WATCHLIST_PATH, watchlist)
            app_log("info", "watchlist_page", "ticker_added", {"ticker": new_ticker})
            st.rerun()
        elif not new_ticker:
            st.error("Ticker fehlt.")
        else:
            st.warning(f"{new_ticker} ist bereits auf der Watchlist.")
    if action_remove.button("Entfernen", use_container_width=True, disabled=remove_ticker == "-"):
        watchlist = [item for item in watchlist if str(item.get("ticker", "")).upper() != remove_ticker]
        write_json(WATCHLIST_PATH, watchlist)
        app_log("info", "watchlist_page", "ticker_removed", {"ticker": remove_ticker})
        st.rerun()
    action_refresh.caption("Watchlist ist nur Beobachtung. Research erzeugt keine Watchlist-Eintraege automatisch.")

    rows = []
    for item in watchlist:
        ticker = str(item.get("ticker", "")).upper()
        payload = payload_for_ticker(ticker, cards)
        snapshot = snapshot_for_ticker(ticker)
        metrics = metrics_for_company(ticker, payload, snapshot)
        rows.append(
            {
                "ticker": ticker,
                "name": payload.get("company_name") or snapshot.get("company_name") or "-",
                "score": payload.get("growth_research_score", "-"),
                "gate": payload.get("gate", "-"),
                "price": format_metric_value(metrics.get("price"), "currency"),
                "peg": format_metric_value(metrics.get("peg"), "multiple"),
                "ev_sales": format_metric_value(metrics.get("ev_to_sales"), "multiple"),
                "next_earnings": format_metric_value(metrics.get("next_earnings_date"), "text"),
                "note": item.get("note", ""),
            }
        )

    main_col, side_col = st.columns([1.85, 0.95], gap="medium")
    with main_col:
        with panel("Beobachtungsliste", "Kompakte Tabelle mit Research-Status und Kernkennzahlen."):
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True, height=420)
            else:
                render_empty("Watchlist ist leer.", ["Ticker hinzufuegen", "Research-Seite nutzen"])
    with side_col:
        render_filter_queue_panel()
        render_market_sentiment_panel()


def render_filter_queue_panel() -> None:
    with panel("Filter Queue", "Watchlist entries promoted by news flow and sentiment."):
        queue = read_json(FILTER_QUEUE_PATH, default=[])
        if not queue:
            render_empty("No filter queue entries.", ["Run data worker", "Sync watchlist", "Check sentiment feeds"])
            return
        st.dataframe(queue[:12], use_container_width=True, hide_index=True, height=210)


def render_market_sentiment_panel() -> None:
    with panel("Market Sentiment", "Aggregated market context from RSS, macro and sentiment classification."):
        market = read_json(MARKET_SNAPSHOT_PATH, default={})
        if not market:
            render_empty("No market snapshot yet.", ["Run worker", "Fetch macro", "Build sentiment snapshot"])
            return

        sentiment = market.get("sentiment", {})
        macro = market.get("macro", {})
        top = st.columns(3, gap="small")
        top[0].metric("Regime", str(market.get("market_regime", "-")))
        top[1].metric("Sentiment", str(sentiment.get("label", "-")))
        top[2].metric("Score", str(sentiment.get("score", "-")))

        st.dataframe(
            [
                {"metric": "fed_funds_rate", "value": macro.get("fed_funds_rate")},
                {"metric": "core_cpi", "value": macro.get("core_cpi")},
                {"metric": "unemployment_rate", "value": macro.get("unemployment_rate")},
                {"metric": "ten_year_treasury", "value": macro.get("ten_year_treasury")},
            ],
            use_container_width=True,
            hide_index=True,
            height=180,
        )


def render_company_search_bar(universe: list[str], cards: list[dict[str, Any]]) -> str:
    options = universe or DEFAULT_UNIVERSE
    current = st.session_state.get("selected_ticker", options[0])
    if current not in options:
        current = options[0]
    with panel("Unternehmen suchen", "Ticker frei eingeben oder vorhandene Research-Artefakte auswaehlen."):
        col_custom, col_select, col_watch, col_status = st.columns([1.2, 1.1, 0.58, 0.78], gap="small")
        custom = col_custom.text_input(
            "Freie Suche",
            placeholder="Ticker oder Name, z.B. NVDA, Microsoft, ASML",
            label_visibility="collapsed",
        ).upper().strip()
        selected = col_select.selectbox(
            "Vorhandene Unternehmen",
            options,
            index=options.index(current),
            format_func=lambda ticker: company_label(ticker, cards),
            label_visibility="collapsed",
        )
        if custom:
            selected = resolve_company_query(custom, options, cards)
        st.session_state["selected_ticker"] = selected
        payload = payload_for_ticker(selected, cards)
        snapshot = snapshot_for_ticker(selected)
        in_watchlist = selected in watchlist_tickers()
        if col_watch.button(
            "+ Watch" if not in_watchlist else "Gemerkt",
            use_container_width=True,
            disabled=in_watchlist or selected == "UNKNOWN",
        ):
            watchlist = read_json(WATCHLIST_PATH, default=[])
            watchlist.append({"ticker": selected, "note": "from search bar"})
            write_json(WATCHLIST_PATH, watchlist)
            app_log("info", "watchlist", "ticker_added_from_search", {"ticker": selected})
            st.rerun()
        source_bits = []
        if payload:
            source_bits.append("card")
        if snapshot:
            source_bits.append("snapshot")
        col_status.markdown(
            f"""
            <div class="selector-state">
              <div class="selector-ticker">{escape_html(selected)}</div>
              <div class="selector-source">{escape_html(', '.join(source_bits) if source_bits else 'no local data')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        app_log("debug", "company", "company_selected", {"ticker": selected, "sources": source_bits})
        return selected


def render_company_selector(universe: list[str], cards: list[dict[str, Any]]) -> str:
    return render_company_search_bar(universe, cards)


def render_research_action_bar(selected_ticker: str) -> None:
    cols = st.columns([0.95, 0.95, 0.75, 1.55], gap="small")
    if cols[0].button("Research inkl. DeepSeek", use_container_width=True, type="primary"):
        run_selected_research(selected_ticker, phase=1, allow_llm=True)
    if cols[1].button("Nur Daten/Smoke", use_container_width=True):
        run_selected_research(selected_ticker, phase=0, allow_llm=False)
    if cols[2].button("Aktualisieren", use_container_width=True):
        app_log("debug", "research_action_bar", "manual_refresh_requested", {"ticker": selected_ticker})
        st.rerun()
    last = st.session_state.get("last_run_state")
    if last:
        cols[3].caption(f"Letzter Run: {last.get('ticker')} -> {last.get('status')} ({last.get('run_id')})")
    else:
        cols[3].caption("Phase 1 nutzt DeepSeek, wenn DEEPSEEK_API_KEY/.env und Kontingent verfuegbar sind.")


def render_data_availability_notice(ticker: str, payload: dict[str, Any], snapshot: dict[str, Any]) -> None:
    if payload or snapshot:
        return
    last = st.session_state.get("last_run_state", {})
    messages = [
        f"Fuer {ticker} liegen noch keine lokalen Research-Daten vor.",
        "Starte Research inkl. DeepSeek, damit zuerst ein Snapshot und danach eine Research Card erzeugt wird.",
    ]
    if str(last.get("ticker", "")).upper() == ticker.upper():
        messages.append(f"Letzter Run: {last.get('status', 'unknown')}")
        for error in last.get("errors", [])[:3]:
            messages.append(f"Error: {error}")
    with panel("Keine Daten fuer diese Auswahl", "Diagnose statt leerer Seite."):
        render_terminal_lines(messages, height=140)


def run_selected_research(ticker: str, phase: int, allow_llm: bool) -> None:
    ticker = ticker.upper().strip()
    if not ticker or ticker == "UNKNOWN":
        app_log("warning", "research_action_bar", "run_rejected", {"reason": "ticker_missing"})
        st.error("Bitte erst ein Unternehmen oder Ticker eingeben.")
        return
    if phase >= 1:
        with st.spinner(f"Daten-Snapshot fuer {ticker} wird gesucht..."):
            ensure_snapshot_for_research(ticker)
    config = PlatformConfig.from_env(phase=phase)
    if allow_llm:
        config = PlatformConfig(
            project_root=config.project_root,
            phase=config.phase,
            audit_dir=config.audit_dir,
            snapshots_dir=config.snapshots_dir,
            cards_dir=config.cards_dir,
            evidence_dir=config.evidence_dir,
            rejected_dir=config.rejected_dir,
            journal_dir=config.journal_dir,
            allow_llm=True,
        )
    app_log("info", "research_action_bar", "pipeline_run_requested", {"ticker": ticker, "phase": phase, "allow_llm": allow_llm})
    with st.spinner(f"Research fuer {ticker} laeuft..."):
        try:
            state = run_pipeline(ticker, config=config)
        except Exception as exc:
            app_log("error", "research_action_bar", "pipeline_run_failed", {"ticker": ticker, "phase": phase}, exc=exc)
            raise
    st.session_state["last_run_state"] = state
    app_log(
        "info",
        "research_action_bar",
        "pipeline_run_completed",
        {"ticker": ticker, "phase": phase, "run_id": state.get("run_id"), "status": state.get("status")},
    )
    st.success(f"{ticker}: {state.get('status')} ({state.get('run_id')})")
    st.rerun()


def ensure_snapshot_for_research(ticker: str) -> None:
    existing = snapshot_for_ticker(ticker)
    if existing and existing.get("metrics"):
        app_log("debug", "data_snapshot", "snapshot_reused", {"ticker": ticker})
        return
    try:
        from data.sources.intelligence_adapter import MultiSourceSnapshotBuilder

        builder = MultiSourceSnapshotBuilder()
        market_snapshot = builder.fetch_market_snapshot()
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        MARKET_SNAPSHOT_PATH.write_text(json.dumps(market_snapshot, indent=2, sort_keys=True), encoding="utf-8")
        snapshot = builder.fetch_snapshot(ticker, market_snapshot=market_snapshot)
        write_json(SNAPSHOTS_DIR / f"{ticker.upper()}.json", snapshot)
        app_log("info", "data_snapshot", "snapshot_created", {"ticker": ticker, "quality_errors": snapshot.get("quality_errors", [])})
    except Exception as exc:
        app_log("error", "data_snapshot", "snapshot_fetch_failed", {"ticker": ticker}, exc=exc)
        raise


def render_research_metrics_panel(
    ticker: str,
    payload: dict[str, Any],
    snapshot: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    title = f"Research.md Kennzahlenmatrix - {ticker}"
    subtitle = "PEG, Scores, Growth, Margins, Quality, Valuation, Dilution and Trading Gate."
    with panel(title, subtitle):
        if not payload and not snapshot:
            render_empty(
                "Noch keine lokalen Daten fuer dieses Unternehmen.",
                ["Snapshot anlegen", "Phase 1 laufen lassen", "Kennzahlen bleiben unknown"],
            )
        quick_cols = st.columns(6, gap="small")
        quick_items = [
            ("PEG", metrics.get("peg"), "multiple"),
            ("EV/Sales", metrics.get("ev_to_sales"), "multiple"),
            ("EV/GP", metrics.get("ev_to_gross_profit"), "multiple"),
            ("Rule 40", metrics.get("rule_of_40"), "percent"),
            ("SBC/Rev", metrics.get("sbc_to_revenue"), "percent"),
            ("ROIC", metrics.get("roic"), "percent"),
        ]
        for col, (label, value, kind) in zip(quick_cols, quick_items, strict=True):
            col.markdown(
                f"""
                <div class="research-kpi">
                  <div class="research-kpi-label">{escape_html(label)}</div>
                  <div class="research-kpi-value">{escape_html(format_metric_value(value, kind))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        tabs = st.tabs(list(RESEARCH_METRIC_GROUPS.keys()) + ["All"])
        for tab, (group, definitions) in zip(tabs[:-1], RESEARCH_METRIC_GROUPS.items(), strict=True):
            with tab:
                st.dataframe(
                    metric_rows_for_group(group, definitions, metrics),
                    use_container_width=True,
                    hide_index=True,
                    height=260,
                )
        with tabs[-1]:
            st.dataframe(all_metric_rows(metrics), use_container_width=True, hide_index=True, height=360)


def render_trader_overview_panel(
    ticker: str,
    payload: dict[str, Any],
    snapshot: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    company = payload.get("company_name") or snapshot.get("company_name") or ticker
    sector = payload.get("sector") or snapshot.get("sector") or "unknown"
    industry = payload.get("industry") or snapshot.get("industry") or "unknown"
    with panel("Trader Overview", "Was ein Profi zuerst braucht: Preis, Trend, Bewertung, Qualitaet, Sentiment und Event-Risiko."):
        st.markdown(
            f"""
            <div class="company-hero">
              <div>
                <div class="company-name">{escape_html(company)}</div>
                <div class="company-meta">{escape_html(ticker)} | {escape_html(sector)} | {escape_html(industry)}</div>
              </div>
              <div class="company-badge">{escape_html(str(payload.get('gate', 'no gate')))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        key_cols = st.columns(8, gap="small")
        items = [
            ("Price", metrics.get("price"), "currency"),
            ("MCap", metrics.get("market_cap_usd"), "large_currency"),
            ("PEG", metrics.get("peg"), "multiple"),
            ("Fwd P/E", metrics.get("forward_pe"), "multiple"),
            ("EV/Sales", metrics.get("ev_to_sales"), "multiple"),
            ("ROIC", metrics.get("roic"), "percent"),
            ("RSI", metrics.get("rsi_14"), "number"),
            ("Earnings", metrics.get("next_earnings_date"), "text"),
        ]
        for col, (label, value, kind) in zip(key_cols, items, strict=True):
            col.markdown(
                f"""
                <div class="research-kpi">
                  <div class="research-kpi-label">{escape_html(label)}</div>
                  <div class="research-kpi-value">{escape_html(format_metric_value(value, kind))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        left, right = st.columns([1.4, 1.0], gap="medium")
        with left:
            render_price_chart(metrics)
        with right:
            render_score_chart(payload)


def render_metric_chart_panel(metrics: dict[str, Any]) -> None:
    with panel("Kennzahlen-Grafiken", "Komprimierter Aktienfinder-Blick auf Wachstum, Marge, Bewertung, Qualitaet und Risiko."):
        tabs = st.tabs(list(TRADER_CHART_GROUPS.keys()) + ["Sentiment"])
        for tab, (group, definitions) in zip(tabs[:-1], TRADER_CHART_GROUPS.items(), strict=True):
            with tab:
                rows = chart_rows_for_group(definitions, metrics)
                if rows:
                    import pandas as pd

                    df = pd.DataFrame(rows).set_index("metric")
                    st.bar_chart(df["value"], height=250)
                    st.dataframe(
                        [
                            {"metric": row["metric"], "value": row["display"], "raw_key": row["raw_key"]}
                            for row in rows
                        ],
                        use_container_width=True,
                        hide_index=True,
                        height=170,
                    )
                else:
                    render_empty("Keine numerischen Werte fuer diese Grafik.", ["Snapshot erweitern", "Phase 1 laufen lassen"])
        with tabs[-1]:
            render_metric_sentiment_hint(metrics)


def render_research_score_panel(payload: dict[str, Any]) -> None:
    with panel("Growth Research Score", "Score blocks A-G from research.md section 9.1, not a trade signal."):
        score = payload.get("growth_research_score", "unknown") if payload else "unknown"
        gate = payload.get("gate", "unknown") if payload else "unknown"
        confidence = payload.get("confidence", "unknown") if payload else "unknown"
        cols = st.columns([0.7, 0.7, 0.8, 1.8], gap="small")
        cols[0].metric("Score", score)
        cols[1].metric("Gate", gate)
        cols[2].metric("Confidence", confidence)
        cols[3].markdown(
            """
            <div class="score-note">
              Research-Score beschreibt die Qualitaet der Wachstumsthese. Er ist kein Kauf- oder Trade-Signal.
            </div>
            """,
            unsafe_allow_html=True,
        )
        breakdown = payload.get("score_breakdown", {}) if payload else {}
        st.dataframe(score_rows(breakdown), use_container_width=True, hide_index=True, height=286)


def render_all_available_metrics_panel(metrics: dict[str, Any], payload: dict[str, Any], snapshot: dict[str, Any]) -> None:
    with panel("Alle verfuegbaren Kennzahlen", "Alles, was lokal aus Snapshot, Research Card, News, Sentiment und LLM-Metadaten ableitbar ist."):
        rows = all_available_rows(metrics, payload, snapshot)
        if not rows:
            render_empty("Noch keine Rohdaten vorhanden.", ["Ticker suchen", "Research inkl. DeepSeek starten"])
            return
        search = st.text_input("Metrik filtern", placeholder="peg, margin, sentiment, llm, source", label_visibility="collapsed")
        if search:
            needle = search.lower()
            rows = [
                row
                for row in rows
                if needle in row["path"].lower() or needle in row["value"].lower() or needle in row["source"].lower()
            ]
        st.dataframe(rows, use_container_width=True, hide_index=True, height=420)


def render_company_status_panel(
    ticker: str,
    payload: dict[str, Any],
    snapshot: dict[str, Any],
    completeness: dict[str, int],
) -> None:
    with panel("Company Status", "Data coverage and local artifacts for the selected company."):
        metric_row(
            [
                ("Ticker", ticker, "selected"),
                ("Card", "yes" if payload else "no", payload.get("research_date", "missing") if payload else "missing"),
                ("Snapshot", "yes" if snapshot else "no", snapshot.get("as_of", "missing") if snapshot else "missing"),
            ],
            compact=True,
        )
        st.progress(completeness["pct"] / 100 if completeness["total"] else 0)
        st.caption(f"Research metric coverage: {completeness['filled']} of {completeness['total']} fields")
        missing = completeness.get("missing", [])
        if missing:
            render_terminal_lines([f"missing: {item}" for item in missing[:9]], height=170)


def render_sentiment_news_panel(payload: dict[str, Any], snapshot: dict[str, Any]) -> None:
    with panel("Sentiment & News", "Katalysatoren, Nachrichtenlage und DeepSeek-Status."):
        company_sent = payload.get("company_sentiment") or snapshot.get("sentiment", {}).get("company", {})
        market_sent = payload.get("market_sentiment") or snapshot.get("sentiment", {}).get("market", {})
        cols = st.columns(2, gap="small")
        cols[0].metric("Company", company_sent.get("label", "unknown"), f"Score {company_sent.get('score', 'unknown')}")
        cols[1].metric("Market", market_sent.get("label", "unknown"), f"Score {market_sent.get('score', 'unknown')}")

        llm = payload.get("llm_metadata", {}) if payload else {}
        if llm:
            if llm.get("error"):
                st.error(f"DeepSeek: {llm.get('error')}")
            else:
                usage = llm.get("usage", {})
                st.caption(
                    f"DeepSeek: {llm.get('model', 'unknown')} | "
                    f"in {usage.get('prompt_tokens', 'unknown')} / out {usage.get('completion_tokens', 'unknown')}"
                )
        else:
            st.caption("DeepSeek: noch keine LLM-Spur fuer diese Auswahl.")

        news = payload.get("news_digest") or snapshot.get("news", {}).get("company", [])
        if news:
            rows = [
                {
                    "sent": item.get("sentiment_label", "-"),
                    "score": item.get("sentiment_score", "-"),
                    "source": item.get("source", "-"),
                    "title": item.get("title", "-"),
                }
                for item in news[:8]
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True, height=235)
        else:
            render_empty("Keine News im Snapshot.", ["Data worker starten", "Research laufen lassen"])


def render_risk_register_panel(payload: dict[str, Any]) -> None:
    with panel("Risiko-Register", "Red Flags, Hard Blocker, offene Fragen und Falsifikation."):
        rows = []
        for key in ["hard_blockers", "red_flags", "bear_case", "open_questions", "falsification_tests"]:
            for item in payload.get(key, []) if payload else []:
                rows.append({"type": key, "item": item})
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True, height=245)
        else:
            render_empty("Noch keine Risikoliste.", ["Phase 1 ausfuehren", "Red-Team erzeugen"])


def render_gate_matrix_for_company(payload: dict[str, Any]) -> None:
    with panel("Gate Matrix", "Selected company gate status."):
        checks = [
            ("research_card", bool(payload)),
            ("score_breakdown", bool(payload.get("score_breakdown")) if payload else False),
            ("PEG_visible", True),
            ("red_team_required", True),
            ("paper_trade_block", current_phase() < 2),
        ]
        cols = st.columns(len(checks), gap="small")
        for col, (label, ok) in zip(cols, checks, strict=True):
            col.markdown(
                f"""
                <div class="check-tile compact-check">
                  <div class="check-state {'ok' if ok else 'warn'}">{'OK' if ok else 'MISS'}</div>
                  <div class="check-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_latest_artifacts(cards: list[dict[str, Any]]) -> None:
    with panel("Latest Artifacts", "Cards, red-team reports and status markers."):
        if not cards:
            render_empty("No cards yet.", ["Run Phase 0 smoke test", "Add local snapshot", "Run Phase 1 research"])
            return
        rows = []
        for card in cards[:10]:
            payload = card.get("payload", {})
            rows.append(
                {
                    "ticker": payload.get("ticker", card["path"].stem.split("_")[0]),
                    "score": payload.get("growth_research_score", "-"),
                    "gate": payload.get("gate", "-"),
                    "category": payload.get("category", "-"),
                    "status": payload.get("status", "-"),
                    "file": card["path"].name,
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True, height=260)


def render_gate_matrix(cards: list[dict[str, Any]]) -> None:
    with panel("Gate Matrix", "Compact view of what the system would block before any human decision."):
        if not cards:
            render_terminal_lines(
                [
                    "research_card: missing",
                    "red_team: waiting",
                    "screener: waiting",
                    "risk_engine: disabled in phase 1",
                    "execution: human gate locked",
                ],
                height=170,
            )
            return
        latest = cards[0].get("payload", {})
        checks = [
            ("research_complete", latest.get("status") in {"research_complete", "screener_passed"}),
            ("red_team_required", True),
            ("screener_required", latest.get("handoff_to_trade_engine") is True),
            ("paper_trade_block", current_phase() < 2),
            ("broker_import_block", True),
        ]
        cols = st.columns(len(checks), gap="small")
        for col, (label, ok) in zip(cols, checks, strict=True):
            col.markdown(
                f"""
                <div class="check-tile">
                  <div class="check-state {'ok' if ok else 'warn'}">{'PASS' if ok else 'WAIT'}</div>
                  <div class="check-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_latest_audit(run: dict[str, Any] | None) -> None:
    with panel("Latest Audit Stream", "JSONL events, newest run first."):
        if not run:
            render_empty("No audit run found.", ["Run pipeline", "Open audit terminal", "Check local filesystem"])
            return
        events = load_audit_events(run["run_id"], AUDIT_DIR)
        lines = []
        for event in events[-9:]:
            payload = event.get("payload", {})
            suffix = ""
            if "status" in payload:
                suffix = f" -> {payload['status']}"
            elif "ticker" in payload:
                suffix = f" {payload['ticker']}"
            lines.append(f"{short_time(event['timestamp'])} {event['event_type']}{suffix}")
        render_terminal_lines(lines, height=260)


def render_snapshot_panel(snapshots: list[Path]) -> None:
    with panel("Data Snapshots", "Local source files that can feed the phase-1 pipeline."):
        if not snapshots:
            render_terminal_lines(
                [
                    "data/snapshots/*.json: empty",
                    "phase_1_card: blocked until Pflichtfelder exist",
                    "worker: python -m apps.workers.data_pipeline.run NVDA",
                ],
                height=170,
            )
            return
        rows = []
        for path in snapshots[-8:]:
            payload = read_json(path, default={})
            rows.append(
                {
                    "ticker": payload.get("ticker", path.stem),
                    "as_of": payload.get("as_of", "-"),
                    "metrics": len(payload.get("metrics", {})),
                    "quality": len(payload.get("quality_errors", [])),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True, height=180)


def render_bottom_command_strip() -> None:
    st.markdown(
        """
        <div class="command-strip">
          <span>$ python -m pipeline.run NVDA --phase 0</span>
          <span>$ python -m pipeline.run NVDA --phase 1</span>
          <span>$ python -m scripts.replay &lt;run_id&gt;</span>
          <span>$ python scripts/check_forbidden_imports.py</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_full_audit() -> None:
    app_log("debug", "page", "render_full_audit")
    cards = load_card_index()
    universe = build_company_universe(cards)
    render_title("Deep Research Audit", "Vollbild-Research: freie Suche, alle Kennzahlen, Charts, Scores, Sentiment und Risiken.")

    selected_ticker = render_company_search_bar(universe, cards)
    render_research_action_bar(selected_ticker)

    payload = payload_for_ticker(selected_ticker, cards)
    snapshot = snapshot_for_ticker(selected_ticker)
    metrics = metrics_for_company(selected_ticker, payload, snapshot)
    completeness = research_metric_completeness(metrics)
    render_data_availability_notice(selected_ticker, payload, snapshot)

    metric_row(
        [
            ("Score", str(payload.get("growth_research_score", "unknown")), payload.get("gate", "no gate")),
            ("Research Data", f"{completeness['filled']}/{completeness['total']}", f"{completeness['pct']}% filled"),
            ("PEG", format_metric_value(metrics.get("peg"), "multiple"), "valuation/growth"),
            ("Rule 40", format_metric_value(metrics.get("rule_of_40"), "percent"), "growth + FCF margin"),
            ("DeepSeek", "error" if payload.get("llm_metadata", {}).get("error") else payload.get("llm_metadata", {}).get("provider", "missing"), "LLM audit"),
        ]
    )

    main_col, side_col = st.columns([2.1, 0.95], gap="medium")
    with main_col:
        render_trader_overview_panel(selected_ticker, payload, snapshot, metrics)
        render_metric_chart_panel(metrics)
        render_research_metrics_panel(selected_ticker, payload, snapshot, metrics)
        render_all_available_metrics_panel(metrics, payload, snapshot)
    with side_col:
        render_research_score_panel(payload)
        render_sentiment_news_panel(payload, snapshot)
        render_risk_register_panel(payload)
        render_company_status_panel(selected_ticker, payload, snapshot, completeness)


def render_card_summary(payload: dict[str, Any]) -> None:
    top = st.columns([1, 1, 1, 1], gap="small")
    top[0].metric("Ticker", payload.get("ticker", "-"))
    top[1].metric("Score", payload.get("growth_research_score", "-"))
    top[2].metric("Gate", payload.get("gate", "-"))
    top[3].metric("Confidence", payload.get("confidence", "-"))

    left, right = st.columns([1.2, 1], gap="medium")
    with left:
        with panel("Thesis", "Cautious research language only."):
            st.write(payload.get("thesis_summary", "unknown"))
        with panel("Score Breakdown", "Blocks from research.md section 9.1."):
            breakdown = payload.get("score_breakdown", {})
            if breakdown:
                st.dataframe(
                    [{"block": key, "points": value} for key, value in breakdown.items()],
                    use_container_width=True,
                    hide_index=True,
                    height=250,
                )
            else:
                render_empty("No score breakdown.", ["Missing deterministic score"])
    with right:
        with panel("Risk Register", "Bear case, hard blockers and open questions."):
            items = []
            for key in ["bear_case", "red_flags", "hard_blockers", "open_questions"]:
                for value in payload.get(key, []):
                    items.append({"type": key, "item": value})
            if items:
                st.dataframe(items, use_container_width=True, hide_index=True, height=330)
            else:
                render_empty("No risk items recorded.", ["Red-team still required"])
        with panel("Sentiment & LLM", "News tone, market context and DeepSeek token usage."):
            llm_metadata = payload.get("llm_metadata", {})
            sentiment_rows = [
                {"scope": "company", **payload.get("company_sentiment", {})},
                {"scope": "market", **payload.get("market_sentiment", {})},
            ]
            st.dataframe(sentiment_rows, use_container_width=True, hide_index=True, height=120)
            st.dataframe(
                [
                    {"field": "provider", "value": llm_metadata.get("provider")},
                    {"field": "model", "value": llm_metadata.get("model")},
                    {"field": "prompt_tokens", "value": llm_metadata.get("usage", {}).get("prompt_tokens")},
                    {"field": "completion_tokens", "value": llm_metadata.get("usage", {}).get("completion_tokens")},
                ],
                use_container_width=True,
                hide_index=True,
                height=160,
            )
            news_digest = payload.get("news_digest", [])
            if news_digest:
                st.dataframe(news_digest[:5], use_container_width=True, hide_index=True, height=180)


def render_audit_terminal() -> None:
    app_log("debug", "page", "render_audit_terminal")
    runs = load_run_index()
    render_title("Audit Terminal", "Replay-oriented event browser. Verbose by design, compact like a terminal.")
    if not runs:
        with panel("Audit", "No JSONL streams available."):
            render_empty("No audit files found.", ["Run pipeline from Ops Desk"])
        return

    left, right = st.columns([0.85, 2.15], gap="medium")
    with left:
        with panel("Runs", "Select a run id."):
            selected = st.radio(
                "Runs",
                runs,
                format_func=lambda run: f"{run['timestamp']}  {run['run_id'][:10]}  {run['event_count']} ev",
                label_visibility="collapsed",
            )
            app_log("debug", "audit", "run_selected", {"run_id": selected["run_id"], "path": selected["path"]})
            st.caption(selected["path"])
    with right:
        events = load_audit_events(selected["run_id"], AUDIT_DIR)
        with panel("Event Stream", selected["run_id"]):
            filters = st.multiselect(
                "Event filter",
                sorted({event["event_type"] for event in events}),
                default=sorted({event["event_type"] for event in events}),
            )
            filtered = [event for event in events if event["event_type"] in filters]
            rows = [
                {
                    "time": short_time(event["timestamp"]),
                    "event": event["event_type"],
                    "payload": compact_json(event.get("payload", {}), 140),
                }
                for event in filtered
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True, height=420)
            render_code_block("\n".join(json.dumps(event, sort_keys=True) for event in filtered), "json", height=260)


def render_approval_queue() -> None:
    app_log("debug", "page", "render_approval_queue")
    queue = awaiting_cards()
    render_title("Approval Queue", "Human-in-the-loop station. Buttons stay locked until a reason is substantial.")
    if not queue:
        left, right = st.columns([1.2, 1], gap="medium")
        with left:
            with panel("Queue Status", "No human decision is currently requested."):
                render_terminal_lines(
                    [
                        "awaiting_human: 0",
                        "phase_1: risk/paper-trade path disabled",
                        "operator_action: review latest research cards",
                        "guardrail: no approval without documented reason",
                    ],
                    height=230,
                )
        with right:
            with panel("Decision Rules", "Same rules apply when queue fills."):
                st.markdown(
                    """
                    - Reason must be at least 20 characters.
                    - Approve, defer and reject are journal events.
                    - Approval is not an order.
                    - Risk and execution gates remain deterministic.
                    """
                )
        return

    for path, payload in queue:
        with panel(path.name, "Awaiting human decision."):
            cols = st.columns([1.1, 1.1, 1.1, 2.4], gap="small")
            cols[0].metric("Ticker", payload.get("ticker", "-"))
            cols[1].metric("Score", payload.get("growth_research_score", "-"))
            cols[2].metric("Gate", payload.get("gate", "-"))
            reason = cols[3].text_area("Decision reason", key=f"reason-{path.stem}")
            locked = len(reason.strip()) < 20
            actions = st.columns(3, gap="small")
            if actions[0].button("Approve", disabled=locked, use_container_width=True, key=f"approve-{path.stem}"):
                app_log("info", "approval", "approve_clicked", {"card": path.name, "reason_length": len(reason)})
            if actions[1].button("Defer", disabled=locked, use_container_width=True, key=f"defer-{path.stem}"):
                app_log("info", "approval", "defer_clicked", {"card": path.name, "reason_length": len(reason)})
            if actions[2].button("Reject", disabled=locked, use_container_width=True, key=f"reject-{path.stem}"):
                app_log("info", "approval", "reject_clicked", {"card": path.name, "reason_length": len(reason)})
            st.json(payload)


def render_knowledge_base() -> None:
    app_log("debug", "page", "render_knowledge_base")
    render_title("Knowledge Base", "Journal, lessons, reviews and proposed learning material.")
    journal_tab, lessons_tab, reviews_tab = st.tabs(["Journal", "Lessons", "Reviews"])
    with journal_tab:
        entries = sorted(JOURNAL_DIR.glob("*.md"), reverse=True)
        if not entries:
            render_empty("No journal entries.", ["Run Phase 1", "Decision events will append here"])
        else:
            selected = st.selectbox("Journal day", entries, format_func=lambda path: path.name)
            app_log("debug", "journal", "journal_day_selected", {"path": str(selected)})
            st.markdown(selected.read_text(encoding="utf-8"))
    with lessons_tab:
        cols = st.columns(3, gap="medium")
        for col, directory in zip(cols, ["active", "proposed", "retired"], strict=True):
            with col:
                with panel(directory.title(), f"research/lessons/{directory}"):
                    files = sorted((LESSONS_DIR / directory).glob("*.md"))
                    if not files:
                        render_empty("No lessons.", ["monthly review", "manual accept"])
                    for path in files:
                        with st.expander(path.name, expanded=False):
                            st.markdown(path.read_text(encoding="utf-8"))
    with reviews_tab:
        reviews = sorted((JOURNAL_DIR / "reviews").glob("*.md"), reverse=True)
        if not reviews:
            render_empty("No monthly reviews.", ["Review agent is manual", "No auto-write to active lessons"])
        else:
            for path in reviews:
                with st.expander(path.name, expanded=True):
                    st.markdown(path.read_text(encoding="utf-8"))


def render_admin() -> None:
    app_log("debug", "page", "render_admin")
    render_title("Admin", "Prompts, config, calibration and repository safety rails.")
    left, center, right = st.columns([1, 1, 1], gap="medium")
    with left:
        with panel("Prompts", "Active prompt files."):
            for path in sorted(Path("agents").glob("*/prompt.md")):
                with st.expander(str(path), expanded=False):
                    st.markdown(path.read_text(encoding="utf-8"))
    with center:
        with panel("Calibration", "Current deterministic score weights."):
            weights = ROOT / "calibration" / "current_weights.json"
            if weights.exists():
                st.json(read_json(weights, default={}))
            else:
                render_empty("Missing current_weights.json", ["restore calibration file"])
    with right:
        with panel("Safety", "Repository-level limits from Agent.md and Trade.md."):
            render_terminal_lines(
                [
                    "pre_commit: forbidden-trading-imports",
                    "blocked: alpaca, ibapi, ib_insync, ccxt",
                    "secrets: .env only, gitignored",
                    "phase_1: no risk execution path",
                    "broker_api: absent",
                ],
                height=240,
            )


def render_app_log_drawer(force_open: bool = False) -> None:
    if not force_open and not st.session_state.get("show_app_log", False):
        return

    with panel("App Log", f"Letzte {APP_LOG_LIMIT} Frontend-Eintraege. Vollansicht ueber Navigation: App Logs."):
        render_app_log_view(compact=True)


def render_app_logs_page() -> None:
    app_log("debug", "page", "render_app_logs_page")
    render_title("App Logs", f"Letzte {APP_LOG_LIMIT} Eintraege, Error-Schnellfilter und detaillierte Tracebacks.")
    render_app_log_view(compact=False)


def render_app_log_view(compact: bool = False) -> None:
    logs = load_app_logs(limit=APP_LOG_LIMIT)
    with st.container(border=not compact):
        if not logs:
            render_empty("No frontend log entries yet.", ["interact with app", "refresh page"])
            return

        if "log_level_filter" not in st.session_state:
            st.session_state["log_level_filter"] = "all"
        if "log_component_filter" not in st.session_state:
            st.session_state["log_component_filter"] = "all"

        filter_col, component_col, search_col, action_col = st.columns([0.8, 1.0, 1.5, 0.65], gap="small")
        level_options = ["all"] + LOG_LEVELS
        selected_level = filter_col.selectbox(
            "Level",
            level_options,
            index=level_options.index(st.session_state.get("log_level_filter", "all")),
            key="log_level_select",
        )
        st.session_state["log_level_filter"] = selected_level
        components = sorted({entry.get("component", "unknown") for entry in logs})
        component_options = ["all"] + components
        selected_component = component_col.selectbox(
            "Component",
            component_options,
            index=component_options.index(st.session_state.get("log_component_filter", "all"))
            if st.session_state.get("log_component_filter", "all") in component_options
            else 0,
            key="log_component_select",
        )
        st.session_state["log_component_filter"] = selected_component
        search = search_col.text_input("Search", placeholder="message, path, ticker, traceback")
        if action_col.button("Errors", use_container_width=True, type="primary"):
            st.session_state["log_level_filter"] = "error"
            st.rerun()

        filtered = filter_logs(logs, selected_level, selected_component, search)

        rows = []
        for entry in filtered[:APP_LOG_LIMIT]:
            rows.append(
                {
                    "time": short_time(entry.get("timestamp", "")),
                    "level": entry.get("level", "-"),
                    "component": entry.get("component", "-"),
                    "message": entry.get("message", "-"),
                    "details": compact_json(entry.get("details", {}), 180),
                }
            )
        st.caption(f"{len(filtered)} Treffer aus den letzten {len(logs)} Eintraegen")
        st.dataframe(rows, use_container_width=True, hide_index=True, height=260 if compact else 420)

        error_entries = [entry for entry in filtered if entry.get("level") == "error"]
        if error_entries:
            st.markdown('<div class="error-strip">Detailed errors</div>', unsafe_allow_html=True)
            for entry in error_entries[:8 if compact else 20]:
                label = f"{short_time(entry.get('timestamp', ''))} {entry.get('component', '-')} :: {entry.get('message', '-')}"
                with st.expander(label, expanded=True):
                    render_code_block(json.dumps(entry, indent=2, sort_keys=True), language="json", height=420)
        else:
            st.caption("No error entries in the current filter.")

        if not compact:
            with st.expander("Raw JSONL view", expanded=False):
                raw_lines = "\n".join(json.dumps(entry, sort_keys=True) for entry in filtered[:APP_LOG_LIMIT])
                render_code_block(raw_lines, language="json", height=360)


def render_fatal_error(exc: Exception) -> None:
    render_title("Frontend Error", "The app caught an exception and wrote a detailed log entry.")
    with panel("Unhandled Exception", type(exc).__name__):
        st.error(str(exc))
        render_code_block(traceback.format_exc(), language="text", height=420)


def render_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="page-title">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div class="page-clock">{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_row(items: list[tuple[str, str, str]], compact: bool = False) -> None:
    columns = st.columns(len(items), gap="small")
    for col, (label, value, hint) in zip(columns, items, strict=True):
        class_name = "metric-tile compact" if compact else "metric-tile"
        col.markdown(
            f"""
            <div class="{class_name}">
              <div class="metric-label">{label}</div>
              <div class="metric-value">{value}</div>
              <div class="metric-hint">{hint}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def sidebar_metric(label: str, value: int) -> None:
    st.markdown(
        f"""
        <div class="sidebar-metric">
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="panel-heading">
          <div class="panel-title">{title}</div>
          <div class="panel-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.container(border=True)


def render_terminal_lines(lines: list[str], height: int = 220) -> None:
    content = "\n".join(lines)
    render_code_block(content, language="text", height=height)


def render_code_block(content: str, language: str = "text", height: int = 220) -> None:
    st.markdown(
        f"""
        <div class="terminal-box" style="max-height:{height}px">
          <pre><code>{escape_html(content)}</code></pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty(title: str, actions: list[str]) -> None:
    chips = "".join(f"<span>{escape_html(action)}</span>" for action in actions)
    st.markdown(
        f"""
        <div class="empty-state">
          <strong>{escape_html(title)}</strong>
          <div>{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_company_universe(cards: list[dict[str, Any]]) -> list[str]:
    tickers: set[str] = set(DEFAULT_UNIVERSE)
    tickers.update(watchlist_tickers())
    for path in SNAPSHOTS_DIR.glob("*.json"):
        if path.stem.startswith("_"):
            continue
        tickers.add(path.stem.upper())
    for card in cards:
        ticker = card.get("payload", {}).get("ticker")
        if ticker:
            tickers.add(str(ticker).upper())
    return sorted(tickers)


def resolve_company_query(query: str, options: list[str], cards: list[dict[str, Any]]) -> str:
    cleaned = query.upper().strip()
    if not cleaned:
        return options[0] if options else DEFAULT_UNIVERSE[0]
    exact = cleaned.replace("$", "")
    if exact in COMPANY_ALIASES:
        return COMPANY_ALIASES[exact]
    if exact in options:
        return exact
    for ticker in options:
        label = company_label(ticker, cards).upper()
        if cleaned in label:
            return ticker
    compact = "".join(ch for ch in exact if ch.isalnum() or ch in ".-")
    return compact or exact


def watchlist_tickers() -> list[str]:
    watchlist = read_json(WATCHLIST_PATH, default=[])
    return [str(item.get("ticker", "")).upper() for item in watchlist if item.get("ticker")]


def company_short_name(ticker: str, cards: list[dict[str, Any]]) -> str:
    label = company_label(ticker, cards)
    if " - " in label:
        return label.split(" - ", 1)[1][:28]
    return "free search"


def company_label(ticker: str, cards: list[dict[str, Any]]) -> str:
    payload = payload_for_ticker(ticker, cards)
    snapshot = snapshot_for_ticker(ticker)
    name = payload.get("company_name") or snapshot.get("company_name")
    if name and name != "unknown":
        return f"{ticker} - {name}"
    return ticker


def payload_for_ticker(ticker: str, cards: list[dict[str, Any]]) -> dict[str, Any]:
    ticker = ticker.upper()
    for card in cards:
        payload = card.get("payload", {})
        if str(payload.get("ticker", "")).upper() == ticker:
            return payload
    return {}


def snapshot_for_ticker(ticker: str) -> dict[str, Any]:
    if not ticker or ticker == "UNKNOWN":
        return {}
    return read_json(SNAPSHOTS_DIR / f"{ticker.upper()}.json", default={})


def metrics_for_company(ticker: str, payload: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    metrics.update(snapshot.get("metrics", {}) if snapshot else {})
    metrics.update(payload.get("key_metrics", {}) if payload else {})

    aliases = {
        "ev_sales": "ev_to_sales",
        "ev_gross_profit": "ev_to_gross_profit",
        "ntm_pe": "forward_pe",
        "average_daily_volume_30d": "average_daily_dollar_volume_30d",
    }
    for source, target in aliases.items():
        if target not in metrics and source in metrics:
            metrics[target] = metrics[source]

    moat = payload.get("moat_assessment", {}) if payload else {}
    if "moat_rating" not in metrics and moat.get("rating"):
        metrics["moat_rating"] = moat.get("rating")

    if is_missing(metrics.get("peg")):
        forward_pe = numeric(metrics.get("forward_pe"))
        growth = numeric(metrics.get("eps_growth_forward")) or numeric(metrics.get("revenue_growth_5y"))
        if forward_pe is not None and growth and growth > 0:
            growth_percent = growth * 100 if growth <= 1 else growth
            metrics["peg"] = forward_pe / growth_percent if growth_percent else None

    if is_missing(metrics.get("rule_of_40")):
        growth = numeric(metrics.get("revenue_growth_5y"))
        fcf = numeric(metrics.get("fcf_margin_5y"))
        if growth is not None and fcf is not None:
            metrics["rule_of_40"] = growth + fcf if growth <= 1 and fcf <= 1 else (growth + fcf) / 100

    return metrics


def chart_rows_for_group(definitions: list[tuple[str, str, str]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, key, kind in definitions:
        value = numeric(metrics.get(key))
        if value is None:
            continue
        chart_value = value * 100 if kind == "percent" and abs(value) <= 1 else value
        rows.append(
            {
                "metric": label,
                "value": chart_value,
                "display": format_metric_value(metrics.get(key), kind),
                "raw_key": key,
            }
        )
    return rows


def render_price_chart(metrics: dict[str, Any]) -> None:
    chart_data = metrics.get("chart_history", [])
    if chart_data:
        import pandas as pd

        df = pd.DataFrame(chart_data)
        if "date" in df and "close" in df:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            columns = [col for col in ["close", "sma_50", "sma_200"] if col in df]
            st.line_chart(df[columns], height=280)
            return
    fallback_rows = []
    for label, key in [("Price", "price"), ("SMA 50", "sma_50"), ("SMA 200", "sma_200"), ("52w high", "week_52_high")]:
        value = numeric(metrics.get(key))
        if value is not None:
            fallback_rows.append({"metric": label, "value": value})
    if fallback_rows:
        import pandas as pd

        df = pd.DataFrame(fallback_rows).set_index("metric")
        st.bar_chart(df["value"], height=280)
    else:
        render_empty("Keine Chartdaten.", ["Snapshot mit chart_history erweitern", "Technische Kennzahlen laden"])


def render_score_chart(payload: dict[str, Any]) -> None:
    breakdown = payload.get("score_breakdown", {}) if payload else {}
    rows = []
    for letter, label, key, max_points in SCORE_BLOCKS:
        points = numeric(breakdown.get(key))
        rows.append({"block": f"{letter} {label[:18]}", "value": round((points or 0) / max_points * 100, 1)})
    if rows:
        import pandas as pd

        df = pd.DataFrame(rows).set_index("block")
        st.bar_chart(df["value"], height=280)
    else:
        render_empty("Keine Scores.", ["Phase 1 Research starten", "Score Breakdown erzeugen"])


def render_metric_sentiment_hint(metrics: dict[str, Any]) -> None:
    rows = []
    for label, key in [
        ("Analyst recommendation", "analyst_recommendation_score"),
        ("Analyst count", "analyst_recommendation_total"),
        ("Last earnings surprise", "last_earnings_surprise"),
        ("Days since 52w high", "days_since_52w_high"),
    ]:
        value = metrics.get(key)
        rows.append({"metric": label, "value": format_metric_value(value, "number"), "raw_key": key})
    st.dataframe(rows, use_container_width=True, hide_index=True, height=190)


def research_metric_completeness(metrics: dict[str, Any]) -> dict[str, Any]:
    definitions = [item for values in RESEARCH_METRIC_GROUPS.values() for item in values]
    missing = [label for label, key, _kind in definitions if is_missing(metrics.get(key))]
    total = len(definitions)
    filled = total - len(missing)
    pct = round((filled / total) * 100) if total else 0
    return {"total": total, "filled": filled, "pct": pct, "missing": missing}


def metric_rows_for_group(
    group: str,
    definitions: list[tuple[str, str, str]],
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for label, key, kind in definitions:
        value = metrics.get(key)
        rows.append(
            {
                "group": group,
                "metric": label,
                "value": format_metric_value(value, kind),
                "raw_key": key,
                "status": "missing" if is_missing(value) else "available",
            }
        )
    return rows


def all_metric_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, definitions in RESEARCH_METRIC_GROUPS.items():
        rows.extend(metric_rows_for_group(group, definitions, metrics))
    return rows


def all_available_rows(metrics: dict[str, Any], payload: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in sorted(metrics.items()):
        if not is_scalar(value):
            continue
        rows.append({"source": "merged_metrics", "path": key, "value": format_raw_value(value)})
    rows.extend(flatten_payload("card", payload, max_depth=3))
    rows.extend(flatten_payload("snapshot", snapshot, max_depth=3))
    deduped: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        deduped[(row["source"], row["path"], row["value"])] = row
    return list(deduped.values())


def flatten_payload(source: str, payload: Any, prefix: str = "", max_depth: int = 2) -> list[dict[str, str]]:
    if max_depth < 0 or payload in ({}, [], None):
        return []
    rows: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if is_scalar(value):
                rows.append({"source": source, "path": path, "value": format_raw_value(value)})
            elif isinstance(value, dict):
                rows.extend(flatten_payload(source, value, path, max_depth - 1))
            elif isinstance(value, list):
                rows.append({"source": source, "path": path, "value": f"{len(value)} items"})
                for index, item in enumerate(value[:6]):
                    rows.extend(flatten_payload(source, item, f"{path}[{index}]", max_depth - 1))
    return rows


def is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def format_raw_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def score_rows(breakdown: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for letter, label, key, max_points in SCORE_BLOCKS:
        points = numeric(breakdown.get(key))
        if points is None:
            value = "unknown"
            pct = "unknown"
        else:
            value = f"{points:.0f}/{max_points}"
            pct = f"{round((points / max_points) * 100)}%"
        rows.append({"block": letter, "name": label, "points": value, "coverage": pct, "raw_key": key})
    return rows


def format_metric_value(value: Any, kind: str) -> str:
    if is_missing(value):
        return "unknown"
    number = numeric(value)
    if kind == "text":
        return str(value)
    if number is None:
        return str(value)
    if kind == "percent":
        number = number * 100 if abs(number) <= 1 else number
        return f"{number:.1f}%"
    if kind == "currency":
        return f"${number:,.2f}"
    if kind == "large_currency":
        if abs(number) >= 1_000_000_000:
            return f"${number / 1_000_000_000:.1f}B"
        if abs(number) >= 1_000_000:
            return f"${number / 1_000_000:.1f}M"
        return f"${number:,.0f}"
    if kind == "multiple":
        return f"{number:.2f}x"
    return f"{number:.2f}"


def is_missing(value: Any) -> bool:
    return value in (None, "", "unknown", "-", [])


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_card_index() -> list[dict[str, Any]]:
    cards = []
    for path in sorted(CARDS_DIR.glob("*.json"), reverse=True):
        if "_redteam" in path.stem:
            continue
        payload = read_json(path, default={})
        cards.append({"path": path, "payload": payload})
    app_log("debug", "filesystem", "card_index_loaded", {"count": len(cards), "directory": str(CARDS_DIR)})
    return cards


def load_run_index() -> list[dict[str, Any]]:
    runs = []
    for path in AUDIT_DIR.glob("*/*.jsonl"):
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not lines:
                continue
            first = json.loads(lines[0])
            latest = json.loads(lines[-1])
            runs.append(
                {
                    "run_id": path.stem,
                    "path": str(path),
                    "timestamp": short_time(latest.get("timestamp", first.get("timestamp", ""))),
                    "event_count": len(lines),
                    "latest": latest.get("event_type", "-"),
                }
            )
        except (OSError, json.JSONDecodeError) as exc:
            app_log("error", "filesystem", "audit_index_read_failed", {"path": str(path)}, exc=exc)
    sorted_runs = sorted(runs, key=lambda run: run["path"], reverse=True)
    app_log("debug", "filesystem", "run_index_loaded", {"count": len(sorted_runs), "directory": str(AUDIT_DIR)})
    return sorted_runs


def awaiting_cards() -> list[tuple[Path, dict[str, Any]]]:
    queue = []
    for card in load_card_index():
        payload = card["payload"]
        if payload.get("status") == "awaiting_human":
            queue.append((card["path"], payload))
    return queue


def related_redteam_files(card_path: Path) -> list[Path]:
    base = card_path.stem
    ticker = base.split("_")[0]
    return sorted(CARDS_DIR.glob(f"{ticker}_*_redteam.*"), reverse=True)


def count_lesson_files() -> int:
    return sum(1 for directory in ["active", "proposed", "retired"] for _ in (LESSONS_DIR / directory).glob("*.md"))


def current_phase() -> int:
    try:
        return int(PlatformConfig.from_env().phase)
    except ValueError:
        return 0


def trend_text(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "no artifacts"
    latest = cards[0]["payload"].get("research_date", "-")
    return f"latest {latest}"


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": state.get("run_id"),
        "ticker": state.get("ticker"),
        "phase": state.get("phase"),
        "status": state.get("status"),
        "errors": state.get("errors", []),
    }


def compact_json(payload: Any, max_len: int) -> str:
    value = json.dumps(payload, sort_keys=True)
    return value if len(value) <= max_len else value[: max_len - 3] + "..."


def short_time(value: str) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%m-%d %H:%M:%S")
    except ValueError:
        return value[:19]


def read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            app_log("debug", "filesystem", "json_missing", {"path": str(path)})
            return default
        value = json.loads(path.read_text(encoding="utf-8"))
        app_log("debug", "filesystem", "json_read", {"path": str(path)})
        return value
    except json.JSONDecodeError as exc:
        app_log("error", "filesystem", "json_decode_failed", {"path": str(path)}, exc=exc)
        return default
    except OSError as exc:
        app_log("error", "filesystem", "json_read_failed", {"path": str(path)}, exc=exc)
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    app_log("info", "filesystem", "json_written", {"path": str(path)})


def ensure_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = uuid4().hex
    st.session_state["render_count"] = st.session_state.get("render_count", 0) + 1


def app_log(
    level: str,
    component: str,
    message: str,
    details: dict[str, Any] | None = None,
    exc: Exception | None = None,
) -> None:
    if level not in LOG_LEVELS:
        level = "info"
    payload: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "level": level,
        "component": component,
        "message": message,
        "session_id": str(st.session_state.get("session_id", "unknown")),
        "render_count": st.session_state.get("render_count", 0),
        "details": redact(details or {}),
    }
    if exc is not None:
        payload["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    try:
        APP_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = APP_LOG_DIR / f"{datetime.now().date().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        trim_app_log_file(path, APP_LOG_LIMIT)
    except OSError:
        pass


def load_app_logs(limit: int) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for path in sorted(APP_LOG_DIR.glob("*.jsonl"), reverse=True):
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError as exc:
            logs.append(
                {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "level": "error",
                    "component": "log_viewer",
                    "message": "app_log_read_failed",
                    "details": {"path": str(path)},
                    "error": {"type": type(exc).__name__, "message": str(exc), "traceback": ""},
                }
            )
            continue
        for line in reversed(lines):
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logs.append(
                    {
                        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                        "level": "error",
                        "component": "log_viewer",
                        "message": "app_log_decode_failed",
                        "details": {"path": str(path), "line": line[:240]},
                        "error": {"type": type(exc).__name__, "message": str(exc), "traceback": ""},
                    }
                )
            if len(logs) >= limit:
                return logs
    return logs


def trim_app_log_file(path: Path, limit: int) -> None:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) <= limit:
            return
        path.write_text("\n".join(lines[-limit:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def filter_logs(
    logs: list[dict[str, Any]],
    selected_level: str,
    selected_component: str,
    search: str,
) -> list[dict[str, Any]]:
    needle = search.lower().strip()
    filtered = []
    for entry in logs:
        if selected_level != "all" and entry.get("level") != selected_level:
            continue
        if selected_component != "all" and entry.get("component") != selected_component:
            continue
        if needle and needle not in json.dumps(entry, sort_keys=True).lower():
            continue
        filtered.append(entry)
    return filtered


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def inject_css() -> None:
    st.markdown(
        """
        <style>
          :root {
            --bg: #0b0f14;
            --panel: #101720;
            --panel-2: #121b26;
            --line: #243241;
            --muted: #8fa3b8;
            --text: #e6edf3;
            --accent: #38d39f;
            --accent-2: #5aa7ff;
            --warn: #f5c56b;
            --danger: #ff6b6b;
          }
          .stApp {
            background:
              linear-gradient(180deg, rgba(90, 167, 255, 0.08), transparent 280px),
              var(--bg);
            color: var(--text);
          }
          .block-container {
            max-width: 1500px;
            padding: 1.1rem 1.5rem 2rem;
          }
          section[data-testid="stSidebar"] {
            background: #0a0e13;
            border-right: 1px solid var(--line);
          }
          section[data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
          }
          .brand {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin-bottom: 1rem;
          }
          .brand-mark {
            width: 42px;
            height: 42px;
            border: 1px solid rgba(56, 211, 159, 0.55);
            display: grid;
            place-items: center;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            color: var(--accent);
            background: rgba(56, 211, 159, 0.08);
            border-radius: 8px;
            font-weight: 700;
          }
          .brand-title {
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.1;
          }
          .brand-subtitle, .metric-hint, .panel-subtitle {
            color: var(--muted);
            font-size: 0.76rem;
          }
          .sidebar-rule {
            height: 1px;
            background: var(--line);
            margin: 0.8rem 0;
          }
          .sidebar-metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.35rem 0;
            border-bottom: 1px solid rgba(143, 163, 184, 0.12);
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.82rem;
          }
          .sidebar-metric strong {
            color: var(--accent);
          }
          .mini-log {
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.78rem;
            color: var(--text);
            display: grid;
            gap: 0.25rem;
          }
          .dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            margin-right: 0.45rem;
          }
          .dot.green { background: var(--accent); }
          .dot.yellow { background: var(--warn); }
          .page-title {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid var(--line);
            padding-bottom: 0.75rem;
            margin-bottom: 0.85rem;
          }
          .page-title h1 {
            margin: 0;
            font-size: 1.55rem;
            letter-spacing: 0;
          }
          .page-title p {
            margin: 0.25rem 0 0;
            color: var(--muted);
            font-size: 0.9rem;
          }
          .page-clock {
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            color: var(--accent);
            border: 1px solid rgba(56, 211, 159, 0.35);
            padding: 0.35rem 0.5rem;
            border-radius: 6px;
            font-size: 0.82rem;
          }
          .metric-tile, .check-tile {
            background: linear-gradient(180deg, rgba(18, 27, 38, 0.98), rgba(11, 15, 20, 0.98));
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
            margin-bottom: 0.75rem;
            min-height: 82px;
          }
          .metric-tile.compact {
            min-height: 68px;
            padding: 0.5rem 0.6rem;
          }
          .metric-label, .check-label {
            color: var(--muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          }
          .metric-value {
            font-size: 1.55rem;
            line-height: 1.25;
            font-weight: 750;
          }
          .selector-state {
            border: 1px solid rgba(56, 211, 159, 0.28);
            border-radius: 8px;
            background: rgba(56, 211, 159, 0.06);
            padding: 0.5rem 0.65rem;
            min-height: 44px;
          }
          .selector-ticker {
            color: var(--accent);
            font-weight: 800;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            line-height: 1.1;
          }
          .selector-source {
            color: var(--muted);
            font-size: 0.73rem;
            line-height: 1.2;
          }
          .research-kpi {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(6, 9, 13, 0.56);
            padding: 0.55rem 0.6rem;
            margin-bottom: 0.65rem;
            min-height: 72px;
          }
          .research-kpi-label {
            color: var(--muted);
            font-size: 0.72rem;
            text-transform: uppercase;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          }
          .research-kpi-value {
            color: var(--text);
            font-size: 1.15rem;
            font-weight: 800;
            margin-top: 0.25rem;
          }
          .company-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            border: 1px solid rgba(56, 211, 159, 0.22);
            border-radius: 8px;
            background: rgba(6, 9, 13, 0.62);
            padding: 0.75rem 0.85rem;
            margin-bottom: 0.75rem;
          }
          .company-name {
            color: var(--text);
            font-size: 1.15rem;
            font-weight: 800;
            line-height: 1.2;
          }
          .company-meta {
            color: var(--muted);
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.76rem;
            margin-top: 0.18rem;
          }
          .company-badge {
            border: 1px solid rgba(245, 197, 107, 0.38);
            border-radius: 999px;
            color: #ffe4aa;
            background: rgba(245, 197, 107, 0.08);
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.78rem;
            font-weight: 800;
            padding: 0.35rem 0.65rem;
            white-space: nowrap;
          }
          .score-note {
            border: 1px solid rgba(245, 197, 107, 0.28);
            border-radius: 8px;
            background: rgba(245, 197, 107, 0.07);
            color: #ffe4aa;
            padding: 0.55rem 0.7rem;
            font-size: 0.84rem;
            line-height: 1.35;
          }
          .compact-check {
            min-height: 66px;
            padding: 0.45rem 0.5rem;
          }
          .panel-heading {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 1rem;
            margin-top: 0.2rem;
            margin-bottom: 0.35rem;
          }
          .panel-title {
            font-size: 0.96rem;
            font-weight: 750;
          }
          .terminal-box {
            overflow: auto;
            background: #06090d;
            border: 1px solid rgba(56, 211, 159, 0.25);
            border-radius: 8px;
            padding: 0.7rem;
          }
          .terminal-box pre {
            margin: 0;
            white-space: pre-wrap;
            word-break: break-word;
          }
          .terminal-box code {
            color: #baf7d5;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.78rem;
            line-height: 1.45;
          }
          .empty-state {
            border: 1px dashed rgba(143, 163, 184, 0.34);
            border-radius: 8px;
            padding: 0.8rem;
            background: rgba(18, 27, 38, 0.45);
            color: var(--muted);
          }
          .empty-state strong {
            color: var(--text);
            display: block;
            margin-bottom: 0.55rem;
          }
          .empty-state span, .command-strip span {
            display: inline-block;
            border: 1px solid rgba(143, 163, 184, 0.25);
            border-radius: 999px;
            padding: 0.25rem 0.45rem;
            margin: 0.15rem;
            font-size: 0.75rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          }
          .check-state {
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 0.35rem;
          }
          .check-state.ok { color: var(--accent); }
          .check-state.warn { color: var(--warn); }
          .command-strip {
            margin-top: 0.85rem;
            padding: 0.55rem;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(6, 9, 13, 0.72);
          }
          .error-strip {
            margin: 0.8rem 0 0.35rem;
            padding: 0.45rem 0.6rem;
            border: 1px solid rgba(255, 107, 107, 0.45);
            border-radius: 7px;
            color: #ffc6c6;
            background: rgba(255, 107, 107, 0.09);
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.82rem;
          }
          div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line);
            background: rgba(16, 23, 32, 0.76);
            border-radius: 8px;
          }
          div[data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 8px;
          }
          button[kind="primary"] {
            background: var(--accent) !important;
            color: #06100b !important;
          }
          .stButton > button {
            border-radius: 7px;
            min-height: 2.35rem;
          }
          @media (max-width: 900px) {
            .page-title {
              align-items: flex-start;
              flex-direction: column;
            }
            .block-container {
              padding: 0.8rem;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
