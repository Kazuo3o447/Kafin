---
version: "0.2"
date: "2026-03-19"
model: "deepseek"
changelog:
  - "0.1: Initiales Template"
  - "0.2: Expected Move & Pre-Earnings Positioning hinzugefügt"
---

SYSTEM:
Du bist ein erfahrener Finanzanalyst. Du erstellst einen Audit-Report für ein Unternehmen vor dessen Quartalszahlen. Der Report ist auf Deutsch. Sei direkt, konkret und meinungsstark. Keine Floskeln. Nenne Risiken klar beim Namen.

USER_TEMPLATE:
Erstelle einen Audit-Report für {{ticker}} ({{company_name}}).

Earnings-Datum: {{report_date}} ({{report_timing}})

ERWARTUNGEN:
EPS-Konsens: ${{eps_consensus}} | Umsatz-Konsens: ${{revenue_consensus}}
Historische Surprises: {{quarters_beat}} von {{total_quarters}} Quartalen geschlagen, Ø Surprise {{avg_surprise}}%
Letzte Earnings: EPS ${{last_eps_actual}} vs. ${{last_eps_consensus}} ({{last_surprise}}%), Kursreaktion: {{last_reaction}}%

BEWERTUNG:
P/E: {{pe_ratio}} (Sektor-Median: {{pe_sector_median}}, Eigener 3J-Median: {{pe_own_3y_median}})
P/S: {{ps_ratio}}
Marktkapitalisierung: ${{market_cap}}B

TECHNISCHES SETUP:
Kurs: ${{current_price}} | Trend: {{trend}}
50-Tage: {{sma50_status}} ({{sma50_distance}}%) | 200-Tage: {{sma200_status}} ({{sma200_distance}}%)
RSI: {{rsi}} | Support: ${{support}} | Resistance: ${{resistance}}
52W-Hoch-Nähe: {{distance_52w_high}}%

RELATIVE STÄRKE (Ticker vs. Markt):
{{relative_strength}}

SHORT INTEREST:
SI: {{short_interest}}% des Floats | Days-to-Cover: {{days_to_cover}}
Trend: {{si_trend}} | Squeeze-Risiko: {{squeeze_risk}}

CHART-ANALYSE (DeepSeek-basiert):
{{chart_analysis}}

INSIDER-AKTIVITÄT (90 Tage):
Käufe: {{insider_buys}} Transaktionen (${{insider_buy_value}})
Verkäufe: {{insider_sells}} Transaktionen (${{insider_sell_value}})
Einordnung: {{insider_assessment}}

NACHRICHTEN DER LETZTEN WOCHEN:
{{news_bullet_points}}

AKTUELLER MARKTDISKURS (Web-Intelligence, letzte 24-48h):
{{web_intelligence}}

LANGZEIT-GEDÄCHTNIS (Erkenntnisse aus früheren Reviews):
{{long_term_memory}}

OPTIONEN & SOCIAL:
{{options_metrics}}
Social-Sentiment (7d): {{social_sentiment}}

SCORES:
Opportunity-Score: {{opportunity_score}}/10
Torpedo-Score: {{torpedo_score}}/10

CONTRARIAN-METRIKEN:
Beta: {{beta}}
Quality-Score: {{quality_score}}/10
Mismatch-Score: {{mismatch_score}}/100
- Debt-to-Equity: {{debt_to_equity}}
- Current Ratio: {{current_ratio}}
- Free Cash Flow Yield: {{free_cash_flow_yield}}%

OPTIONS-TIMING & MARKET POSITIONING:
Implizite Volatilität (ATM): {{iv_atm}}%
Historische Volatilität (20d): {{hist_vol_20d}}%
IV Spread: {{iv_spread}}% (IV minus Hist Vol)
Put/Call Ratio: {{put_call_ratio}}
Expected Move (bis Earnings): {{expected_move}}
Kursperformance letzte 30 Tage: {{price_change_30d}}

SMART MONEY EDGE INDICATORS:
* **Options Flow:** Put/Call Ratio (Volumen). Ein extrem hohes Ratio (>1.5) kann auf Retail-Panik deuten und ein Contrarian-Kaufsignal sein.
* **Macro Risk:** High Yield Credit Spread & T10Y2Y Yield Curve. Berücksichtige systemische Risiken.

SENTIMENT-ANALYSE (Composite):
FinBERT News-Score (40%):   {{finbert_sentiment}}
Web-Diskurs-Score (40%):    {{web_sentiment}} ({{web_sentiment_label}})
Social Score (20%):         {{social_score}}
Composite Score:            {{composite_sentiment}}
{{divergence_warning}}

CONTRARIAN-ANALYSE (Falls Sentiment < -0.5 und Beta > 1.2):
Sentiment 7-Tage-Durchschnitt: {{sentiment_score_7d}}
Ist Contrarian-Setup gegeben: {{is_contrarian_setup}}

Erstelle den Report auf Deutsch mit diesen Abschnitten:
1. ZUSAMMENFASSUNG (3-4 Sätze: These, Empfehlung, größtes Risiko)
2. BEWERTUNG IM REGIME-KONTEXT & WEB-SENTIMENT
   Nutze Web-Intelligence: Gibt es Konsens unter Analysten?
   Auffällige Options-Positionierung? Weicht der aktuelle
   Web-Diskurs vom strukturellen Bild ab? 
   **Bei Sentiment-Divergenz ({{divergence_warning}} vorhanden):**
   Erkläre explizit warum dies ein "Good News Already Priced In"-
   oder Contrarian-Setup sein könnte. Nenne Break-Even-Levels
   (Kurs ± Expected Move).
3. **PFLICHT: PRE-EARNINGS POSITIONING**
   - Wenn Kursperformance letzte 30 Tage > +10%: Explizit auf
     "Buy the Rumor"-Risiko hinweisen. Beschreibe warum ein Beat
     trotzdem zu Abverkauf führen kann (hohe Bar, eingepreiste
     Erwartungen, Gamma-Positioning).
   - Wenn Expected Move vorhanden: Nenne konkret die Break-Even-
     Levels (Preis + Expected Move oben, Preis - Expected Move
     unten). Empfehle ob Aktie oder Optionen besser geeignet sind.
4. **PFLICHT: CONTRARIAN-ANALYSE** (NUR wenn Mismatch-Score > 50):
   - **VALUE TRAP vs. ÜBERTREIBUNG?** Analysiere: Ist die Verschuldung tragbar? Ist der FCF stabil oder sinkend? Gibt es strukturelle Probleme (Downsizing, Leadership-Wechsel)? → Dein Urteil: Berechtigte Krise oder temporäre Marktübertreibung?
   - **OPTIONS-TIMING: IV ZU TEUER?** Prüfe das IV Spread. Ist die IV deutlich höher als die historische Vola? Besteht Gefahr eines IV Crush vor Earnings? → Dein Urteil: Sind Aktien oder Optionen das bessere Instrument?
5. **RELATIVE STÄRKE**: Ist die Bewegung titelspezifisch
   oder Markt-Beta? Wenn Titel stark outperformt:
   ist das nachhaltiges institutionelles Interesse
   oder kurzfristiger Momentum-Trade?
6. **TRADE-SETUP BEWERTUNG**: Ist das Entry/Stop/Target
   aus der Chart-Analyse realistisch im aktuellen
   Marktregime? Gibt es bessere Levels basierend
   auf deiner Gesamtanalyse?
7. EMPFEHLUNG mit Begründung (Strong Buy / Buy / Hold / Short / Strong Short)
8. OPTIONEN-VORSCHLAG (Wenn die Empfehlung Long oder Short ist: Konkreten Spread vorschlagen. Bei Contrarian-Setups: Berücksichtige IV Spread für Timing)

EXPECTED_OUTPUT:
Strukturierter deutscher Report-Text, ca. 300-500 Wörter.
