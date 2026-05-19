# research.md

**Version:** 1.0  
**Stand:** 2026-05-15  
**Geltungsbereich:** Researchmodul der privaten Trading-Research-Plattform  
**Status:** verbindlicher Plan, Agenten-Prompt und Bewertungsdokumentation  

---

## 1. Zweck dieser Datei

Diese Datei definiert, wie das Researchmodul der Plattform Wachstumsaktien analysiert, bewertet, klassifiziert und an die Trading-Logik uebergibt.

Das Researchmodul ist **kein Live-Trading-System** und darf niemals Orders an Broker, Boersen, Banken oder externe Handelsplaetze senden. Es erzeugt nur:

- Research Cards,
- Watchlist-Kandidaten,
- Scoring-Tabellen,
- Risikohinweise,
- Paper-Trading-Ideen,
- Red-Team-Kritik,
- Journal- und Lernmaterial.

Die Plattform handelt nie live. Selbst ein sehr guter Research-Score erzeugt nur eine **These**. Ein moeglicher Paper-Trade entsteht erst, wenn auch Marktregime, Liquiditaet, Momentum, technisches Setup, Risiko, Korrelation und Journalregeln aus `Trade.md` erfuellt sind.

Der zentrale Grundsatz lautet:

> Research findet interessante Unternehmen. Trading prueft, ob daraus unter aktuellen Marktbedingungen ueberhaupt ein handelbarer Paper-Trade wird.

---

## 2. Rolle des Researchmoduls innerhalb der Plattform

Das Researchmodul beantwortet nicht die Frage: "Soll ich diese Aktie kaufen?"

Es beantwortet stattdessen:

1. Was ist das Unternehmen?
2. Wodurch entsteht Wachstum?
3. Ist dieses Wachstum profitabel, skalierbar und verteidigbar?
4. Welche Kennzahlen belegen oder widerlegen die These?
5. Ist das Wachstum schon zu stark eingepreist?
6. Welche Risiken koennen die These zerstoeren?
7. Passt die Aktie in eine der Plattform-Kategorien: `Rocket`, `Quality Growth`, `Transitional/Pick-and-Shovel`, `Hype/Risk`, `Broken Growth` oder `Ignore`?
8. Darf die Aktie an den Trade-Screener uebergeben werden?

Das Researchmodul ist damit die fundamentale und qualitative Vorstufe des Tradingprozesses. Es ist kein Ersatz fuer Regimefilter, Momentumfilter, Backtesting, Risiko- und Positionsgroessenlogik.

---

## 3. Zusammenfassung des importierten PDFs

Das PDF `Wachstumsaktien Bewertung_ Kennzahlen und Scoring.pdf` liefert die Grundidee fuer dieses Modul. Es argumentiert, dass Wachstumsaktien nicht ausreichend durch isolierte historische Multiplikatoren wie das KGV bewertet werden koennen. Stattdessen fordert es einen multidimensionalen Ansatz aus:

- Umsatz- und EPS-Wachstum,
- PEG-Ratio,
- Share Count Trend und Verwässerung,
- ROE/ROIC,
- Margenexpansion und Operating Leverage,
- NTM-Multiplikatoren im historischen Kontext,
- CAN SLIM,
- ARR, NRR und wiederkehrenden Umsaetzen,
- Rule of 40, Rule of X und Rule of 20,
- Economic Moats,
- Marktkapitalisierung und Beta,
- Sentiment und alternativen Daten,
- Kategorisierung in `Rocket`, `Quality Growth` und `Kombiniert`.

Die Tabellen auf Seite 16 bis 18 des PDFs sind fuer die Plattform besonders wichtig: Dort werden Wachstumsaktien nach operativer Wachstumsarchitektur, Profitabilitaet, Moat, Heuristiken, Marktkapitalisierung, Beta und Sentiment-Relevanz in Kategorien eingeteilt. Diese Kategorien werden in dieser Datei uebernommen, aber technisch geschaerft und um harte Ausschluss- und Risikoregeln ergaenzt.

---

## 4. Was aus dem PDF uebernommen wird

Folgende Punkte werden als sinnvoll in die Plattform uebernommen:

### 4.1 KGV ist bei Wachstumsaktien allein unzureichend

Ein hohes KGV kann bei stark skalierenden Unternehmen weniger problematisch sein als ein niedriges KGV bei stagnierenden Unternehmen. Fuer die Plattform ist deshalb nicht das absolute KGV entscheidend, sondern die Frage:

> Ist die Bewertung plausibel im Verhaeltnis zu Wachstum, Margenpotenzial, Kapitalrendite, Verwässerung, Risiko und Moat?

### 4.2 Wachstum muss qualitativ bewertet werden

Umsatzwachstum allein reicht nicht. Die Plattform muss unterscheiden zwischen:

- organischem Wachstum,
- akquisitionsgetriebenem Wachstum,
- preisgetriebenem Wachstum,
- volumengetriebenem Wachstum,
- zyklischem Wachstum,
- einmaligem Sonderboom,
- wiederkehrendem Wachstum.

### 4.3 Verwässerung ist ein zentrales Warnsignal

Viele Wachstumsunternehmen zeigen optisch starke Umsaetze, aber Aktionaere werden durch Stock-Based Compensation und steigende Aktienanzahl verwässert. Die Plattform muss daher zwingend auswerten:

- diluted shares outstanding,
- YoY Share Count Growth,
- SBC als Anteil am Umsatz,
- SBC als Anteil am operativen Cashflow,
- FCF vor und nach SBC,
- Buybacks relativ zur Verwässerung,
- Net Share Repurchase Yield.

### 4.4 Moat ist wichtiger als Story

Eine Wachstumsstory ohne verteidigbaren Wettbewerbsvorteil ist fragil. Das PDF uebernimmt zu Recht die klassischen Moat-Quellen:

- Netzwerkeffekte,
- Wechselkosten,
- immaterielle Vermoegenswerte,
- Kostenvorteile,
- effiziente Skalierung.

Diese qualitative Analyse wird in der Plattform mit quantitativen Spuren kombiniert:

- ROIC ueber WACC,
- stabile Bruttomargen,
- Marktanteil,
- Retention,
- Pricing Power,
- Kundenkonzentration,
- Kapitalintensitaet.

### 4.5 Kategorien sind nuetzlich

Die PDF-Kategorien `Rocket`, `Quality Growth` und `Kombiniert` sind fuer die Plattform brauchbar. Sie werden aber erweitert, weil ein Trading-System auch negative Kategorien benoetigt:

- `Hype/Risk`,
- `Dilution Trap`,
- `Value Trap`,
- `Broken Growth`,
- `Too Hard`,
- `Ignore`.

---

## 5. Was am PDF kritisch zu sehen ist

Das PDF enthaelt gute Ideen, ist aber zu selbstsicher formuliert. Agenten duerfen es nicht als Wahrheit behandeln, sondern als Hypothesensammlung.

### 5.1 Zu viel Gewissheit

Formulierungen wie "mit absoluter Gewissheit" sind fuer Finanzmaerkte ungeeignet. Research arbeitet mit Wahrscheinlichkeiten, nicht mit Gewissheiten.

Korrekte Plattformformulierung:

> Die Kennzahlen erhoehen oder senken die Plausibilitaet einer These. Sie beweisen keine zukuenftige Outperformance.

### 5.2 Survivorship Bias

Das PDF nennt Unternehmen wie Palantir, Axon, Micron, Hims & Hers, Microsoft und Lumentum. Diese Beispiele koennen lehrreich sein, aber sie bergen Rueckschaufehler.

Agenten muessen immer fragen:

- Welche aehnlichen Unternehmen sahen damals ebenfalls vielversprechend aus und scheiterten?
- Welche Signale haetten vorab wirklich unterschieden?
- War der Erfolg fundamental vorhersehbar oder erst nachtraeglich erklaerbar?

### 5.3 Fundamentalanalyse ist nicht automatisch Trading-Edge

Ein gutes Unternehmen ist nicht automatisch ein guter Trade. Eine Aktie kann fundamental stark sein und trotzdem kurzfristig fallen, wenn:

- Erwartungen zu hoch sind,
- Bewertung perfektes Wachstum einpreist,
- Zinsen steigen,
- der Sektor rotiert,
- Momentum bricht,
- institutionelle Anleger Gewinne realisieren.

Deshalb gilt:

> Research-Score != Trade-Signal.

### 5.4 Alternative Daten sind teuer und fehleranfaellig

Professionelle alternative Daten wie Kreditkartendaten, Satellitendaten, Channel Checks oder proprietaere Sentimentfeeds sind fuer ein privates Projekt meist teuer, lizenziert und schwer replizierbar. Die Plattform darf solche Daten als Konzept kennen, aber im MVP nur oeffentliche, guenstige Proxys verwenden.

Beispiele fuer guenstige Proxys:

- Google Trends,
- App-Store-Rankings und Reviews,
- GitHub-Aktivitaet,
- Web-Traffic-Schaetzungen,
- Job-Postings,
- Produktbewertungen,
- offizielle Kundenkennzahlen,
- Earnings-Call-Transkripte,
- Pressemitteilungen,
- SEC-Filings.

Diese Proxys bekommen immer einen niedrigeren Confidence Score als gepruefte Finanzdaten.

### 5.5 PEG ist fragil

PEG basiert auf erwarteten Wachstumsraten. Diese Erwartungen sind unsicher, besonders bei fruehen Wachstumsunternehmen. PEG darf nur sector-relative und nie isoliert genutzt werden.

### 5.6 ROE kann verzerrt sein

ROE kann durch Verschuldung, Aktienrueckkaeufe, geringe Buchwerte oder negative Eigenkapitalbasen verzerrt werden. Die Plattform bevorzugt deshalb:

- ROIC,
- Gross Profit / Assets,
- FCF Margin,
- FCF Conversion,
- ROIC - WACC Spread,
- Margenstabilitaet.

### 5.7 NRR, ARR und Rule of 40 sind nicht universell

NRR und ARR sind vor allem fuer SaaS und abonnementaehnliche Modelle aussagekraeftig. Fuer Hardware, Halbleiter, Banken, Versicherungen, Biotech, Industrie und Einzelhandel muessen andere KPIs verwendet werden.

### 5.8 TAM-Narrative sind gefaehrlich

Ein grosser Total Addressable Market beweist nichts. Entscheidend ist:

- Welche reale Kundengruppe zahlt heute?
- Wie hoch ist die Penetration?
- Wie schnell sinken Kundengewinnungskosten?
- Gibt es Pricing Power?
- Wird Wachstum durch echte Nachfrage oder durch Rabatte erkauft?
- Kann das Unternehmen Marktanteile profitabel halten?

---

## 6. Erweiterung durch aktuelle Research-Grundlagen

### 6.1 Quality ist ein eigener Faktor

Die Plattform bewertet Wachstum nie ohne Qualitaet. In der Quality-Minus-Junk-Forschung wird Qualitaet ueber Profitabilitaet, Wachstum, Sicherheit und Ausschüttung bzw. Kapitaldisziplin beschrieben. Fuer unsere Plattform heisst das:

> Hohe Wachstumsraten bekommen nur dann einen hohen Score, wenn sie mit Kapitaldisziplin, Bilanzsicherheit und operativer Qualitaet kombiniert sind.

### 6.2 Profitabilitaet ist nicht altmodisch, sondern zentral

Das Fama-French-Fuenf-Faktoren-Modell ergaenzt die klassischen Faktoren um Profitabilitaet und Investment. Fuer Growth-Research ist das entscheidend: Starkes Wachstum bei schwacher Profitabilitaet und aggressiver Kapitalbindung ist weniger attraktiv als Wachstum mit steigender Kapitalrendite.

Novy-Marx zeigt zudem, dass Gross Profitability eine wichtige Renditeinformation enthaelt. Deshalb soll die Plattform nicht nur Nettoergebnis betrachten, sondern besonders:

- Gross Profit / Assets,
- Gross Margin Trend,
- Gross Margin Stability,
- Operating Margin Trend,
- FCF Conversion.

### 6.3 Economic Moat muss quantitativ und qualitativ geprueft werden

Morningstar definiert Wide Moat als Wettbewerbsvorteil mit erwarteter Dauer von ueber 20 Jahren und Narrow Moat als Vorteil von etwa 10 Jahren. S&P nutzt fuer quantitative Moat-Methodiken Kennzahlen wie Bruttomarge, Bruttomargenstabilitaet, ROIC und Marktanteil.

Die Plattform kombiniert deshalb:

- qualitative Moat-Quelle,
- Moat-Dauer,
- Moat-Trend,
- ROIC-Stabilitaet,
- Margenstabilitaet,
- Marktanteilsentwicklung,
- Kundenbindung,
- Pricing Power.

### 6.4 Rule of 40 wird durch Rule of X ergaenzt

Die klassische Rule of 40 addiert Umsatzwachstum und Profitabilitaetsmarge. Fuer Cloud- und SaaS-Unternehmen ist das ein guter Start, aber nicht ausreichend. Die Rule of X gewichtet Wachstum hoeher als kurzfristige Profitabilitaet, sofern das Wachstum effizient und verteidigbar ist.

Plattformregel:

- Fruehe SaaS-Rockets: Wachstum wird staerker gewichtet, aber nur mit Cash-Runway und fallendem Burn.
- Reife SaaS-Unternehmen: FCF-Marge, NRR, Net Expansion, SBC und Rule of X zaehlen staerker.
- Nicht-SaaS-Unternehmen: Rule of 40 nur verwenden, wenn das Geschaeftsmodell wirklich wiederkehrend und softwareaehnlich ist.

### 6.5 SBC ist echte wirtschaftliche Kostenquelle

Stock-Based Compensation ist nicht einfach "non-cash". Sie kann Aktionaere verwaessern und Bewertungskennzahlen verzerren. Die Plattform muss deshalb zwei Versionen jeder Profitabilitaetsanalyse erzeugen:

1. Reported / GAAP oder IFRS.
2. Owner-adjusted: FCF und EPS unter Beruecksichtigung von SBC und Verwässerung.

### 6.6 Analystenrevisionen sind wichtiger als absolute Kursziele

Absolute Kursziele sind oft verrauscht und interessengeleitet. Wichtiger ist die Richtung der Erwartungen:

- EPS-Revisions nach oben,
- Umsatzrevisionen nach oben,
- Margenrevisionen nach oben,
- Guidance-Erhoehungen,
- sinkende Dispersion der Schaetzungen,
- Revisionen ueber mehrere Wochen.

### 6.7 PEAD ist nuetzlich, aber kein Earnings-Roulette

Post-Earnings-Announcement Drift kann nach positiven Ueberraschungen auftreten, ist aber je nach Marktsegment, Liquiditaet und Zeitperiode unterschiedlich stark. Die Plattform nutzt Earnings nicht als Blindkauf-Signal. Sie beobachtet:

- Earnings Surprise,
- Guidance Surprise,
- Kursreaktion am Earnings-Tag,
- Volumen,
- ob das Gap gehalten wird,
- ob Analystenrevisionen folgen,
- ob ein kontrollierter Pullback entsteht.

Keine Paper-Trades direkt vor Earnings, ausser ein eigener getesteter Earnings-Prozess existiert spaeter explizit.

---

## 7. Datenhierarchie und Evidenzqualitaet

Jede Research-Aussage bekommt eine Quelle und einen Confidence Score.

### 7.1 Evidenzklassen

| Klasse | Quelle | Confidence |
|---|---|---:|
| A | SEC 10-K, 10-Q, 8-K, Jahresbericht, testierte Finanzberichte | sehr hoch |
| A- | Offizielle Investor Relations, Earnings Releases, Shareholder Letters | hoch |
| B | Earnings-Call-Transkripte, Management-Q&A, FactSet/Refinitiv/Analystenkonsens | mittel bis hoch |
| B- | Branchenberichte, Marktstudien, seriöse Finanzdatenanbieter | mittel |
| C | Presseartikel, Interviews, Podcasts, Newsletter | niedrig bis mittel |
| D | Social Media, Reddit, X, YouTube, Foren | niedrig |
| E | Unbelegte Blogposts, KI-generierte Inhalte ohne Quellen | sehr niedrig |

Agenten muessen unsichere Daten klar markieren. Keine Kennzahl darf erfunden werden. Wenn Daten fehlen, lautet die Ausgabe: `unknown`.

---

## 8. Universum und Vorfilter

Das Researchmodul darf grundsaetzlich viele Unternehmen analysieren. An den Trade-Screener duerfen aber nur Aktien uebergeben werden, die die Plattformregeln erfuellen.

### 8.1 Harte Vorfilter fuer Paper-Trading-Kandidaten

Eine Aktie darf nur weitergereicht werden, wenn sie:

- liquide handelbar ist,
- keine Microcap-Spekulation ist,
- keine Penny-Stock-Struktur hat,
- einen engen Spread besitzt,
- kein Hebelprodukt, CFD, Turbo, Optionsschein oder Derivat ist,
- nicht unmittelbar vor einem Hochrisiko-Event steht,
- nicht durch fehlende Daten unbewertbar ist.

### 8.2 Research ohne Trading-Freigabe

Auch nicht handelbare Unternehmen koennen im Researchmodul analysiert werden. Sie erhalten dann den Status:

`Research Only - Not Eligible For Paper Trading`

---

## 9. Growth Research Score: 0 bis 100 Punkte

Der Growth Research Score ist der zentrale fundamentale Score des Researchmoduls. Er ist **kein Kaufsignal**. Er beschreibt nur die Qualitaet und Attraktivitaet der Wachstumsthese.

### 9.1 Gewichtung

| Block | Gewicht | Ziel |
|---|---:|---|
| A. Wachstum und Marktchance | 18 | Ist das Wachstum real, gross und nachhaltig? |
| B. Unit Economics und Margen | 14 | Wird Wachstum effizienter oder teurer? |
| C. Qualitaet und Moat | 18 | Ist die Rendite verteidigbar? |
| D. Bewertung relativ zu Wachstum | 14 | Ist die Aktie fuer die These plausibel bewertet? |
| E. Kapitaldisziplin und Verwässerung | 12 | Kommt Wachstum bei Aktionaeren an? |
| F. Katalysatoren, Revisionen und Sentiment | 12 | Gibt es aktuelle Nachfrage nach der Aktie? |
| G. Risiko und Fragilitaet | 12 | Was kann die These zerstoeren? |
| **Summe** | **100** |  |

---

## 10. Block A: Wachstum und Marktchance - 18 Punkte

### 10.1 Metriken

- Umsatzwachstum YoY,
- Umsatz-CAGR 3 Jahre,
- organisches Wachstum,
- ARR-Wachstum bei SaaS,
- NRR / Net Dollar Retention,
- Kundenwachstum,
- Wachstum pro Kunde,
- neue Produktlinien,
- Marktanteilsgewinne,
- reale TAM-Penetration.

### 10.2 Scoring

| Bewertung | Beschreibung | Punkte |
|---|---|---:|
| schwach | Wachstum < Markt/Sektor oder ruecklaeufig | 0-4 |
| solide | 10-20 % Wachstum, aber ohne klare Beschleunigung | 5-8 |
| stark | 20-40 % Wachstum, organisch und wiederholbar | 9-13 |
| sehr stark | > 40 %, mit Kunden- und Segmentbelegen | 14-16 |
| aussergewoehnlich | > 40 % plus steigende Retention, Share Gains und neue TAM-Belege | 17-18 |

### 10.3 Red Flags

- Wachstum nur durch Akquisitionen,
- Wachstum durch Rabattierung,
- sinkender Umsatz pro Kunde,
- stark steigende Churn,
- grosse Diskrepanz zwischen Bookings und Umsatz,
- Management spricht nur ueber TAM, aber nicht ueber reale Penetration.

---

## 11. Block B: Unit Economics und Margen - 14 Punkte

### 11.1 Metriken

- Bruttomarge,
- Bruttomargenstabilitaet,
- operative Marge,
- FCF-Marge,
- EBITDA-Marge,
- Contribution Margin,
- Customer Acquisition Cost,
- Lifetime Value,
- Payback Period,
- Operating Leverage,
- Rule of 40,
- Rule of X,
- Rule of 20 fuer IT-Services.

### 11.2 Branchenlogik

| Branche | Wichtige Kennzahlen |
|---|---|
| SaaS / Cloud | ARR, NRR, GRR, Rule of 40, Rule of X, FCF-Marge, SBC |
| Marketplace / Plattform | GMV, Take Rate, Netzwerkeffekte, Contribution Margin |
| Hardware / Halbleiter | Zyklusposition, Bruttomarge, Lagerbestand, CapEx, Auslastung |
| Healthcare / Telemedizin | Kundenbindung, regulatorische Risiken, Gross Margin, CAC |
| Industrie / Pick-and-Shovel | Auftragsbestand, Book-to-Bill, Kundendiversifikation, CapEx-Zyklus |
| IT-Services | organisches Wachstum + EBITA-Marge, Rule of 20 |

### 11.3 Red Flags

- Umsatzwachstum steigt, aber Bruttomarge sinkt dauerhaft,
- Vertriebskosten wachsen schneller als Umsatz,
- FCF bleibt negativ trotz Reife,
- Rule of 40 wird nur durch Wachstum erfuellt, waehrend Burn eskaliert,
- Management ignoriert SBC.

---

## 12. Block C: Qualitaet und Moat - 18 Punkte

### 12.1 Moat-Quellen

Agenten muessen jede Moat-Behauptung einer oder mehreren Quellen zuordnen:

| Moat-Quelle | Prueffragen |
|---|---|
| Netzwerkeffekt | Wird das Produkt mit jedem Nutzer wertvoller? Gibt es Winner-takes-most-Dynamik? |
| Wechselkosten | Waere ein Kundenwechsel teuer, riskant oder operativ schmerzhaft? |
| Immaterielle Assets | Marken, Patente, Lizenzen, regulatorische Zulassungen, Datenvorsprung? |
| Kostenvorteil | Kann das Unternehmen dauerhaft guenstiger produzieren oder vertreiben? |
| Effiziente Skalierung | Ist der Markt nur fuer wenige Anbieter profitabel? |

### 12.2 Quantitative Moat-Spuren

- ROIC > WACC ueber mehrere Jahre,
- stabile hohe Bruttomarge,
- niedrige Standardabweichung der Bruttomarge,
- steigender Marktanteil,
- hohe Retention,
- geringe Churn,
- Pricing Power,
- steigender Umsatz pro Kunde,
- hohe Wiederkaufsrate,
- sinkende CAC Payback Period.

### 12.3 Moat-Rating der Plattform

| Rating | Bedeutung |
|---|---|
| Wide Moat | Vorteil plausibel > 20 Jahre haltbar |
| Narrow Moat | Vorteil plausibel 10-20 Jahre haltbar |
| Emerging Moat | Vorteil erkennbar, aber noch nicht bewiesen |
| No Moat | Kein belastbarer Vorteil |
| Negative Moat Trend | Vorteil wird durch Wettbewerb, KI, Regulierung oder Kosten zerstoert |

### 12.4 Red Flags

- hohe Bruttomargen ziehen aggressive Wettbewerber an,
- Produkt ist leicht kopierbar,
- Wachstum haengt von einem einzelnen Vertriebskanal ab,
- Kundenkonzentration > 30 % bei einem Kunden,
- Moat basiert nur auf Management-Narrativ,
- KI oder Open Source koennte das Produkt commoditisieren.

---

## 13. Block D: Bewertung relativ zu Wachstum - 14 Punkte

### 13.1 Bewertungskennzahlen

- Forward P/E,
- EV/Sales,
- EV/Gross Profit,
- EV/EBITDA,
- EV/FCF,
- PEG,
- NTM P/E relativ zum 5-Jahres-Median,
- NTM EV/Sales relativ zum eigenen Verlauf,
- Peer-Vergleich,
- Reverse DCF,
- Szenarioanalyse.

### 13.2 Bewertungsgrundsatz

> Eine Aktie ist nicht teuer, weil ein Multiple hoch ist. Sie ist teuer, wenn die im Kurs enthaltenen Erwartungen unwahrscheinlich hoch sind.

Die Plattform nutzt deshalb immer mindestens drei Perspektiven:

1. **Relative Bewertung:** Vergleich mit Sektor und Peers.
2. **Historische Bewertung:** Vergleich mit eigener Bewertungsbandbreite.
3. **Erwartungsanalyse:** Welche Wachstums- und Margenannahmen sind im Kurs implizit enthalten?

### 13.3 Red Flags

- Bewertung impliziert perfekte Ausfuehrung,
- Multiple expandierte schneller als fundamentale Kennzahlen,
- Umsatzwachstum verlangsamt sich bei gleichbleibender Bewertung,
- Analystenrevisionen fallen, aber Multiple bleibt hoch,
- keine Margin of Safety,
- nur Kursziel-Argumentation ohne Cashflow-Logik.

---

## 14. Block E: Kapitaldisziplin und Verwässerung - 12 Punkte

### 14.1 Metriken

- Share Count Growth YoY,
- diluted shares 3y CAGR,
- SBC / Revenue,
- SBC / Gross Profit,
- SBC / Operating Cash Flow,
- FCF after SBC,
- Net Debt / EBITDA,
- Cash Runway,
- Buyback Yield,
- Net Cash Position,
- Debt Maturity Wall.

### 14.2 Scoring-Logik

| Situation | Bewertung |
|---|---|
| sinkende Aktienanzahl + positiver FCF | sehr positiv |
| stabile Aktienanzahl + FCF positiv | positiv |
| moderate Verwässerung bei sehr starkem Wachstum | neutral bis leicht negativ |
| hohe SBC ohne klare Effizienzsteigerung | negativ |
| steigende Aktienanzahl + negativer FCF + hohe Verschuldung | harter Blocker |

### 14.3 Harte Warnschwellen

Diese Schwellen sind keine automatischen Verbote, aber muessen im Report markiert werden:

- Share Count Growth > 3 % p.a.,
- SBC / Revenue > 10 %,
- SBC / Operating Cash Flow > 30 %,
- Net Debt / EBITDA > 3,
- Cash Runway < 18 Monate,
- Buybacks nur zur Kompensation von SBC ohne echten Rueckkaufnutzen.

---

## 15. Block F: Katalysatoren, Revisionen und Sentiment - 12 Punkte

### 15.1 Katalysatoren

- Earnings Beat,
- Guidance Raise,
- Analystenrevisionen nach oben,
- Produktlaunch,
- neue Grosskunden,
- Regulierungsfreigabe,
- Sektorrotation,
- M&A,
- struktureller Makrotrend,
- fallende Zinsen fuer lang laufende Growth-Cashflows,
- neue Margenziele.

### 15.2 Analystenrevisionen

Die Plattform bewertet nicht das Kursziel selbst, sondern die Aenderung der Erwartungen:

- EPS Revision 1M / 3M,
- Revenue Revision 1M / 3M,
- EBITDA Revision 1M / 3M,
- Anzahl Upgrades vs Downgrades,
- Guidance-Historie,
- Schaetzungsdispersion.

### 15.3 News- und Sentiment-Logik

| Quelle | Nutzung |
|---|---|
| RSS-Finanzfeeds und IR-Feeds | Primaerquelle fuer News-Ingestion, Watchlist-Bezug und Katalysatoren |
| Earnings Calls | Managementtone, Risiken, Guidance |
| Analystenberichte | Revisionen und Diskussionspunkte, nicht blind uebernehmen |
| Markt- und Makro-News | Gesamtmarkt-Sentiment und Regimekontext |
| Social Media | hoechstens Aufmerksamkeitsindikator, kein Alpha-Beweis |

Die operative Logik ist:

1. RSS-Feeds werden regelmaessig fuer Watchlist-Unternehmen, Sektorquellen und Gesamtmarkt abgerufen.
2. News werden Tickern, Themen oder Marktsegmenten zugeordnet.
3. Watchlist-Ticker mit relevanten neuen Meldungen werden automatisch in eine Filter-Queue fuer den naechsten Research-/Screener-Lauf uebernommen.
4. FinBERT klassifiziert jede Nachricht in `positive`, `neutral` oder `negative`.
5. Aus den Einzelmeldungen werden ein Unternehmens-Sentiment und ein Markt-Sentiment aggregiert.
6. Sentiment ist ein Zusatzsignal. Es darf harte Fundamentaldaten-, Liquiditaets- oder Risikoregeln nicht ueberschreiben.

### 15.4 Red Flags

- nur Social-Media-Hype,
- Nachricht ist bereits voll eingepreist,
- Katalysator ist binär und nicht modellierbar,
- hoher News-Flow, aber keine Ergebnisrevisionen,
- Insider verkaufen aggressiv nach positiven Meldungen.

---

## 16. Block G: Risiko und Fragilitaet - 12 Punkte

### 16.1 Risikotypen

- Bewertungsrisiko,
- Zinsrisiko,
- Beta-Risiko,
- Liquiditaetsrisiko,
- Gap-Risiko,
- Kundenkonzentration,
- Lieferkettenrisiko,
- Regulierungsrisiko,
- Bilanzrisiko,
- Verwässerungsrisiko,
- Disruptionsrisiko,
- KI-Kommoditisierungsrisiko,
- Managementrisiko,
- geopolitisches Risiko.

### 16.2 Risk Score

Der Risiko-Block wird invers gewertet: Hohe Fragilitaet senkt den Score.

| Risiko | Wirkung |
|---|---|
| niedriges Beta, stabile Margen, breite Kundenbasis | positiv |
| hohes Beta, aber hohe Qualitaet und liquide Aktie | neutral bis leicht negativ |
| hohe Kundenkonzentration, zyklisches Geschaeft | negativ |
| regulatorisches binaeres Risiko | stark negativ |
| Bilanzstress + negativer FCF | harter Blocker |

---

## 17. Kategorien der Plattform

### 17.1 Rocket

**Definition:** Sehr hohes Wachstum, oft > 40 %, starke Story, hoher TAM, fruehe Marktanteilsgewinne, meist noch begrenzter Moat, hohes Beta.

**Typische Merkmale:**

- starkes Umsatzwachstum,
- hohes ARR/NRR oder schnelle Kundenakquise,
- moeglicherweise negative Gewinne,
- hohe Volatilitaet,
- starke News- und Sentiment-Abhaengigkeit,
- hohe Bewertungsanfälligkeit.

**Plattformregel:**

Rocket-Aktien duerfen nur in Paper Trading gehandelt werden, wenn Liquiditaet, Setup, Risiko und Regime sehr sauber sind. Sie sind Lernobjekte mit hoher Fragilitaet, keine Core-Bausteine.

### 17.2 Quality Growth

**Definition:** Solides bis hohes Wachstum, gute Kapitalrendite, positive FCF-Tendenz, stabiler oder breiter Moat, bessere Planbarkeit.

**Typische Merkmale:**

- Wachstum meist 15-30 %,
- stabilere Margen,
- positive FCF-Marge,
- hohe ROIC/ROE-Qualitaet,
- geringeres Beta als Rockets,
- starke institutionelle Nachfrage.

**Plattformregel:**

Quality Growth ist die bevorzugte Kategorie fuer die erste Plattformphase, weil sie Growth, Momentum und Risikokontrolle besser verbindet.

### 17.3 Transitional / Pick-and-Shovel

**Definition:** Unternehmen an einem zyklischen oder technologischen Wendepunkt. Wachstum kann stark beschleunigen, ist aber oft hardware-, capex- oder kundenkonzentrationsabhaengig.

**Typische Merkmale:**

- zyklische Margen,
- starker operativer Hebel,
- einzelne Grosskunden,
- Lager- und Lieferkettenrisiko,
- hohe Abhaengigkeit von Megatrends.

**Plattformregel:**

Nur handeln, wenn Zyklusdaten, Sektortrend und Momentum bestaetigen. Fundamentale These allein reicht nicht.

### 17.4 Hype/Risk

**Definition:** Hohe Aufmerksamkeit, aber unklare Qualitaet, schwache Zahlen oder ueberzogene Bewertung.

**Plattformregel:**

Keine Paper-Trades, ausser zu Forschungszwecken in separater Beobachtungsliste ohne simulierte Position.

### 17.5 Dilution Trap

**Definition:** Starkes Wachstum, aber Aktionaere werden dauerhaft verwaessert.

**Plattformregel:**

Blocker, bis Share Count, SBC und FCF-Struktur verbessert sind.

### 17.6 Broken Growth

**Definition:** Frueherer Wachstumswert mit fallendem Wachstum, sinkenden Margen, negativen Revisionen und brechendem Momentum.

**Plattformregel:**

Nicht als Long-Kandidat. Nur im Research dokumentieren.

### 17.7 Too Hard

**Definition:** Datenlage, Bilanz, Geschaeftsmodell oder regulatorische Lage sind nicht ausreichend verstandlich.

**Plattformregel:**

Kein Paper-Trade. Agenten muessen `Too Hard` aktiv nutzen, statt Scheingenauigkeit zu erzeugen.

---

## 18. Score-Interpretation

| Score | Bedeutung | Aktion |
|---:|---|---|
| 0-39 | schwach oder unbewertbar | ignorieren |
| 40-54 | Research interessant, aber grosse Defizite | beobachten |
| 55-69 | brauchbare These | Watchlist Research |
| 70-79 | starke These | an Trade-Screener uebergeben |
| 80-89 | sehr starke These | bevorzugte Watchlist, aber kein automatischer Trade |
| 90-100 | aussergewoehnlich | Red-Team-Pflicht wegen Ueberzeugungsrisiko |

Ein hoher Score loest immer eine Red-Team-Frage aus:

> Was muss schiefgehen, damit diese scheinbar starke These falsch ist?

---

## 19. Harte Research-Blocker

Eine Aktie darf trotz gutem Score nicht an die Paper-Trading-Logik uebergeben werden, wenn einer dieser Punkte zutrifft:

- keine belastbaren Finanzdaten,
- laufende Bilanzzweifel oder Going-Concern-Warnung,
- extreme Verwässerung ohne klaren Pfad zur FCF-Deckung,
- Cash Runway < 12 Monate,
- nicht modellierbares binaeres Rechts- oder Zulassungsrisiko,
- extrem breite Spreads,
- Microcap / Penny-Stock-Struktur,
- Kursbewegung fast nur Social-Media-getrieben,
- Earnings oder FDA/Regulierungsentscheidung unmittelbar bevorstehend,
- Bilanz- oder Betrugsverdacht,
- LLM kann die Kernthese nicht mit Quellen belegen.

---

## 20. Research-to-Trade-Gate

Das Researchmodul gibt Kandidaten nur an die Trade-Engine weiter. Es darf nie selbst handeln.

### 20.1 Uebergabe erlaubt, wenn:

- Growth Research Score >= 70,
- keine harten Blocker,
- Daten-Confidence mindestens `medium`,
- Kategorie nicht `Hype/Risk`, `Dilution Trap`, `Broken Growth`, `Too Hard` oder `Ignore`,
- Liquiditaetsdaten vorhanden,
- letzter Earnings-Report ausgewertet,
- Red-Team-Kritik abgeschlossen.

### 20.2 Trade-Engine entscheidet danach separat ueber:

- Marktregime,
- Momentum,
- 52-Wochen-Hoch-Naehe,
- Trend,
- Pullback oder Breakout,
- ATR,
- Stop-Abstand,
- Paper-Positionsgroesse,
- Korrelation mit bestehenden Paper-Positionen,
- Journalpflicht.

### 20.3 Drei Gate-Zustaende

| Gate | Bedeutung |
|---|---|
| Green | darf an Trade-Screener uebergeben werden |
| Yellow | Research interessant, aber offene Fragen |
| Red | blockiert, kein Paper-Trade |

---

## 21. Research-Output-Schema

Jeder Agent muss fuer eine Unternehmensanalyse dieses Schema liefern:

```json
{
  "ticker": "",
  "company_name": "",
  "exchange": "",
  "sector": "",
  "industry": "",
  "research_date": "YYYY-MM-DD",
  "category": "Rocket | Quality Growth | Transitional | Hype/Risk | Dilution Trap | Broken Growth | Too Hard | Ignore",
  "growth_research_score": 0,
  "gate": "Green | Yellow | Red",
  "confidence": "low | medium | high",
  "thesis_summary": "",
  "bull_case": [],
  "bear_case": [],
  "key_metrics": {
    "revenue_growth_yoy": null,
    "revenue_cagr_3y": null,
    "gross_margin": null,
    "operating_margin": null,
    "fcf_margin": null,
    "roic": null,
    "rule_of_40": null,
    "rule_of_x": null,
    "share_count_growth_yoy": null,
    "sbc_to_revenue": null,
    "net_debt_to_ebitda": null,
    "beta": null,
    "ntm_pe": null,
    "ev_sales": null,
    "ev_gross_profit": null,
    "peg": null
  },
  "score_breakdown": {
    "growth_market": 0,
    "unit_economics_margins": 0,
    "quality_moat": 0,
    "valuation": 0,
    "capital_discipline_dilution": 0,
    "catalysts_revisions_sentiment": 0,
    "risk_fragility": 0
  },
  "moat_assessment": {
    "rating": "Wide | Narrow | Emerging | No Moat | Negative Trend | Unknown",
    "sources": [],
    "evidence": [],
    "threats": []
  },
  "catalysts": [],
  "red_flags": [],
  "hard_blockers": [],
  "open_questions": [],
  "falsification_tests": [],
  "source_list": [],
  "handoff_to_trade_engine": false
}
```

---

## 22. Agenten-Prompt fuer das Researchmodul

Der folgende Prompt ist verbindlich fuer Research-Agenten:

```markdown
Du bist ein Research-Agent innerhalb einer privaten Trading-Research-Plattform.

Deine Aufgabe ist nicht, Kaufempfehlungen zu geben. Deine Aufgabe ist, Wachstumsaktien kritisch, quellenbasiert und reproduzierbar zu analysieren. Die Plattform handelt nie live. Deine Ergebnisse duerfen maximal an eine Paper-Trading-Simulation uebergeben werden.

Arbeite nach folgenden Regeln:

1. Behandle jede Wachstumsthese als Hypothese, nicht als Wahrheit.
2. Verwende primaer belastbare Quellen: 10-K, 10-Q, Jahresberichte, Investor-Relations-Dokumente, Earnings Releases, Earnings-Call-Transkripte und gepruefte Finanzdaten.
3. Erfinde keine Kennzahlen. Wenn eine Zahl fehlt, schreibe `unknown`.
4. Trenne harte Zahlen von Management-Narrativen.
5. Berechne keine finalen Scores selbst, wenn die Plattform diese deterministisch berechnet. Du darfst Scores erklaeren und Plausibilitaetschecks liefern.
6. Pruefe immer Verwässerung, SBC, Share Count Trend und FCF-Qualitaet.
7. Pruefe immer, ob Wachstum organisch, wiederkehrend, profitabel und verteidigbar ist.
8. Pruefe immer, ob der Moat qualitativ behauptet und quantitativ sichtbar ist.
9. Unterscheide Rocket, Quality Growth, Transitional/Pick-and-Shovel, Hype/Risk, Dilution Trap, Broken Growth, Too Hard und Ignore.
10. Suche aktiv nach Gegenargumenten und Falsifikationsbedingungen.
11. Social Media ist nur ein Aufmerksamkeits- und Volatilitaetssignal, kein Beweis fuer Alpha.
12. Ein hoher Research-Score ist kein Trade-Signal. Nur die Trade-Engine darf nach separater Pruefung einen Paper-Trade simulieren.
13. Gib am Ende immer `gate`, `confidence`, `hard_blockers`, `red_flags`, `open_questions` und `handoff_to_trade_engine` aus.

Analysiere das Unternehmen nach diesen Bloecken:

A. Wachstum und Marktchance
B. Unit Economics und Margen
C. Qualitaet und Moat
D. Bewertung relativ zu Wachstum
E. Kapitaldisziplin und Verwässerung
F. Katalysatoren, Revisionen und Sentiment
G. Risiko und Fragilitaet

Dein Stil ist kritisch, sachlich, quellenorientiert und vorsichtig. Du vermeidest Uebertreibungen, Hype und Scheingenauigkeit.
```

---

## 23. Red-Team-Prompt

Jede starke These ab Score 75 muss durch einen Red-Team-Agenten geprueft werden:

```markdown
Du bist der Red-Team-Agent der Trading-Research-Plattform.

Deine Aufgabe ist es, eine positiv klingende Wachstumsthese zu zerlegen. Du bist nicht gegen das Unternehmen voreingenommen, aber du suchst systematisch nach Denkfehlern, Datenluecken, Hype, Bewertungsrisiken und versteckten Annahmen.

Beantworte:

1. Welche Annahmen muessen stimmen, damit die These funktioniert?
2. Welche dieser Annahmen sind am unsichersten?
3. Welche Kennzahl koennte die These am schnellsten widerlegen?
4. Ist das Wachstum organisch oder gekauft?
5. Wird Wachstum durch Rabatte, hohe SBC oder Verwässerung erkauft?
6. Gibt es echte Pricing Power oder nur Nachfrage durch einen Zyklus?
7. Ist der Moat belegbar oder nur Management-Sprache?
8. Ist die Bewertung bereits so hoch, dass selbst gute Zahlen enttaeuschen koennen?
9. Welche Risiken ignorieren optimistische Analysten?
10. Welche Gegenbeispiele aus derselben Branche sind gescheitert?
11. Wuerde ich diese These auch ohne steigenden Kurs glauben?
12. Was wuerde mich zwingen, den Score um mindestens 20 Punkte zu senken?

Gib am Ende aus:
- `red_team_verdict`: pass | caution | fail
- `top_5_risks`
- `falsification_triggers`
- `missing_data`
- `recommended_gate`: Green | Yellow | Red
```

---

## 24. Workflow: Von PDF/Research zu Research Card

### 24.1 Dokumenten-Ingestion

Wenn ein neues PDF oder Research-Dokument in den Research-Ordner gelegt wird:

1. Datei registrieren.
2. Hash bilden.
3. Metadaten speichern: Dateiname, Datum, Quelle, Autor falls bekannt.
4. Text extrahieren.
5. Seitenbilder fuer Tabellen und Diagramme rendern.
6. Tabellen separat speichern.
7. Dokument in Chunks teilen.
8. Embeddings erzeugen.
9. In PostgreSQL/pgvector speichern.
10. LLM-Zusammenfassung erzeugen.
11. Extrahierte Frameworks und Kennzahlen als strukturierte Objekte speichern.

### 24.2 Ticker-Extraktion

Der Agent extrahiert:

- Ticker,
- Unternehmensnamen,
- Branchen,
- KPIs,
- Beispielaktien,
- Zeitraeume,
- Quellenbehauptungen.

Er markiert, ob ein Dokument:

- akademisch,
- kommerziell,
- journalistisch,
- brokerbasiert,
- intern,
- unbekannt

ist.

### 24.3 Framework-Extraktion

Aus Research-Dokumenten werden wiederverwendbare Regeln gewonnen:

```json
{
  "framework_name": "Rule of 40",
  "applicable_industries": ["SaaS", "Cloud Software"],
  "formula": "Revenue growth + FCF margin",
  "thresholds": [">= 40"],
  "limitations": ["not universal", "growth and margin not equally valuable in all cases"],
  "source_document": "...",
  "confidence": "medium"
}
```

---

## 25. Datenbedarf des Researchmoduls

### 25.1 Pflichtdaten

- Unternehmensstammdaten,
- Kursdaten,
- Marktkapitalisierung,
- Umsatz,
- Bruttogewinn,
- operativer Gewinn,
- Nettoergebnis,
- operativer Cashflow,
- CapEx,
- Free Cashflow,
- Bilanzdaten,
- Cash und Schulden,
- Share Count basic und diluted,
- SBC,
- Segmentdaten,
- Earnings-Termine,
- Unternehmensberichte.

### 25.2 Wuenschenswerte Daten

- Analystenrevisionen,
- Consensus Estimates,
- NTM-Multiplikatoren,
- Earnings-Call-Transkripte,
- Insidertransaktionen,
- institutionelle Ownership,
- Short Interest,
- Web-Traffic,
- App-Rankings,
- Google Trends,
- GitHub- und Entwickleraktivitaet,
- Produktbewertungen,
- Stellenausschreibungen.

### 25.3 Datenquellen nach Kosten/Nutzen

| Datenart | Kosten/Nutzen | Empfehlung |
|---|---|---|
| SEC EDGAR | sehr gut | Pflicht fuer US-Aktien |
| Unternehmens-IR | sehr gut | Pflicht |
| Yahoo/Stooq/EODHD/Polygon je nach Budget | gut | Kursdaten |
| Financial Modeling Prep / Alpha Vantage / Tiingo je nach Budget | mittel | Fundamentaldaten pruefen |
| Koyfin/TIKR/FactSet/Refinitiv | hoch, aber teuer | optional manuell |
| NewsAPI/GDELT/RSS | gut fuer MVP | News-Proxies |
| Google Trends/App Reviews/GitHub | guenstig, aber noisy | nur als schwache alternative Daten |
| Social Media APIs | noisy und regulatorisch/technisch fragil | nur Aufmerksamkeit/Volatilitaet |

---

## 26. Deterministische Logik vs LLM-Aufgaben

### 26.1 Muss in deterministischem Code bleiben

- Kennzahlenberechnung,
- Score-Normalisierung,
- Z-Scores,
- Percentiles,
- Sector-relative Rankings,
- Share Count Growth,
- SBC-Quoten,
- FCF-Berechnung,
- Rule of 40 / Rule of X / Rule of 20,
- ROIC,
- EV/Sales,
- EV/Gross Profit,
- PEG,
- Beta,
- Volatilitaet,
- Datenvalidierung,
- Gate-Entscheidungen,
- Paper-Trading-Blocker.

### 26.2 Darf an LLMs gehen

- PDF-Zusammenfassung,
- Earnings-Call-Zusammenfassung,
- Moat-Beschreibung,
- qualitative Risikoextraktion,
- Managementtone,
- News-Sentiment,
- Katalysator-Identifikation,
- Red-Team-Kritik,
- Erklaerung von Score-Komponenten,
- Vergleich von Bull- und Bear-Case.

### 26.3 LLM-Verbot

LLMs duerfen nicht:

- finale Kennzahlen erfinden,
- Brokerorders erstellen,
- Live-Trades freigeben,
- Paper-Trades ohne deterministische Gate-Logik freigeben,
- Daten ohne Quelle als Fakt ausgeben,
- Kursziele als Wahrheit behandeln,
- "Buy", "Sell" oder "Strong Buy" als Plattformentscheidung ausgeben.

Erlaubte Formulierung:

> Die Aktie ist ein Research-Kandidat mit Gate Yellow. Fuer einen Paper-Trade fehlen noch Momentum- und Setup-Bestaetigung.

Nicht erlaubte Formulierung:

> Kaufen.

---

## 27. Normalisierung und Score-Berechnung

Alle Scores muessen sector-relative berechnet werden, weil Kennzahlen zwischen Branchen nicht direkt vergleichbar sind.

### 27.1 Grundprinzip

```python
metric_percentile = percentile_rank(metric_value, peer_group)
score_component = weighted_average(metric_percentiles)
```

### 27.2 Peer Groups

Mindestens:

- Sektor,
- Industrie,
- Marktkapitalisierungsklasse,
- Region,
- Geschaeftsmodelltyp.

Beispiele:

- US SaaS Mid Cap,
- US Semiconductors Large Cap,
- EU Industrial Automation Mid Cap,
- Digital Health Small/Mid Cap,
- Cybersecurity Large/Mid Cap.

### 27.3 Winsorizing

Extreme Ausreisser sollen winsorized werden, damit ein einzelner Wert den Score nicht dominiert.

```python
winsorized_value = min(max(value, percentile_5), percentile_95)
```

### 27.4 Missing Data

Fehlende Daten duerfen nicht automatisch als neutral gewertet werden. Regeln:

- Wenn eine wichtige Kennzahl fehlt, sinkt `confidence`.
- Wenn mehrere Pflichtkennzahlen fehlen, Gate = Yellow oder Red.
- LLM darf fehlende Daten nicht schaetzen, ausser explizit als Szenario markiert.

---

## 28. Beispielhafte Score-Formel

```python
growth_research_score = (
    0.18 * growth_market_score
  + 0.14 * unit_economics_score
  + 0.18 * quality_moat_score
  + 0.14 * valuation_score
  + 0.12 * capital_discipline_score
  + 0.12 * catalyst_revision_sentiment_score
  + 0.12 * risk_fragility_score
)
```

Danach werden Blocker angewendet:

```python
if hard_blocker:
    gate = "Red"
    handoff_to_trade_engine = False
elif confidence == "low":
    gate = "Yellow"
    handoff_to_trade_engine = False
elif growth_research_score >= 70:
    gate = "Green"
    handoff_to_trade_engine = True
else:
    gate = "Yellow"
    handoff_to_trade_engine = False
```

---

## 29. Research Card Template

```markdown
# Research Card: {Company} ({Ticker})

## 1. Kurzfazit
- Kategorie:
- Growth Research Score:
- Gate:
- Confidence:
- Handoff an Trade-Engine: ja/nein

## 2. Investment-/Research-These

## 3. Warum ist die Aktie interessant?

## 4. Wichtigste Kennzahlen

| Kennzahl | Wert | Zeitraum | Quelle | Interpretation |
|---|---:|---|---|---|

## 5. Wachstum

## 6. Unit Economics und Margen

## 7. Moat

## 8. Bewertung

## 9. Kapitaldisziplin und Verwässerung

## 10. Katalysatoren und Revisionen

## 11. Risiken

## 12. Red-Team-Kritik

## 13. Falsifikationspunkte

## 14. Offene Fragen

## 15. Entscheidung

Nicht handelbar / Research Only / an Trade-Screener uebergeben.
```

---

## 30. Praktische Leitfragen fuer Wachstumsaktien

### 30.1 Wachstum

- Wächst das Unternehmen schneller als sein Markt?
- Ist das Wachstum organisch?
- Wiederholt sich das Wachstum ueber mehrere Quartale?
- Gibt es Anzeichen fuer Beschleunigung oder Verlangsamung?
- Wird Wachstum durch neue Kunden, hoehere Preise oder hoehere Nutzung getrieben?

### 30.2 Qualitaet

- Steigen Brutto- und operative Marge?
- Verbessert sich FCF?
- Ist ROIC positiv und steigend?
- Ist das Geschaeft kapitalleicht oder kapitalintensiv?
- Gibt es echte Skaleneffekte?

### 30.3 Moat

- Warum kann ein Konkurrent das nicht einfach kopieren?
- Sind Kunden gebunden?
- Hat das Unternehmen Daten-, Marken-, Lizenz- oder Kostenvorteile?
- Werden Vorteile staerker oder schwaecher?

### 30.4 Bewertung

- Welche Erwartungen sind im Kurs enthalten?
- Wie viel Wachstum ist schon eingepreist?
- Was passiert bei 10 % weniger Wachstum?
- Was passiert bei 200 Basispunkten weniger Marge?
- Liegt die Bewertung ueber oder unter dem eigenen Verlauf?

### 30.5 Verwässerung

- Kommt Wachstum pro Aktie an?
- Steigt EPS schneller als Umsatz?
- Steigt FCF pro Aktie?
- Kompensieren Buybacks echte Verwässerung oder nur SBC?

### 30.6 Risiken

- Was ist die groesste Abhaengigkeit?
- Was kann das Narrativ in einem Quartal zerstoeren?
- Gibt es regulatorische oder bilanzielle Risiken?
- Ist die Aktie zinssensitiv?
- Ist die Bewertung so hoch, dass gute Zahlen nicht reichen?

---

## 31. Verbindung zu `Trade.md`

`research.md` erweitert `Trade.md`, ersetzt es aber nicht.

Die Reihenfolge lautet:

1. Researchmodul findet und klassifiziert interessante Unternehmen.
2. Trade-Screener prueft Liquiditaet, Momentum, 52-Wochen-Hoch, Trend, Regime und Setup.
3. Risk Engine prueft ATR, Stop, Positionsgroesse, Korrelation und Paper-Portfolio-Risiko.
4. Journalmodul dokumentiert die Idee.
5. Paper-Trading-Simulation darf nur erfolgen, wenn alle Gates gruene Freigabe geben.

Keine Komponente darf Live-Trading ausloesen.

---

## 32. Minimaler MVP fuer das Researchmodul

### Phase 1: Dokumenten-Research

- PDFs in `research/inbox/` ablegen.
- Text und Tabellen extrahieren.
- Zusammenfassung erzeugen.
- Frameworks extrahieren.
- Research-Wissensbasis aufbauen.

### Phase 2: Unternehmens-Research Cards

- Ticker eingeben.
- Finanzdaten laden.
- Kennzahlen berechnen.
- LLM erzeugt qualitative Analyse.
- Red-Team-Agent prueft These.
- Score und Gate speichern.

### Phase 3: Watchlist-Handoff

- Nur Gate Green an Trade-Screener.
- Watchlist-Ticker mit relevantem News-Impuls duerfen automatisch in die Filter-Queue aufgenommen werden.
- Trade-Screener prueft technische und risikobasierte Kriterien.
- Kein Live-Trading, nur Paper-Trading-Simulation.

---

## 33. Dateistruktur fuer Research

Empfohlene Struktur im Repository:

```text
research/
  inbox/                    # neue PDFs, Artikel, Reports
  processed/                # bereits verarbeitete Originale
  rejected/                 # unbrauchbare oder doppelte Quellen
  cards/                    # generierte Research Cards als Markdown
  frameworks/               # extrahierte Bewertungsframeworks
  prompts/                  # Research- und Red-Team-Prompts
  exports/                  # CSV/JSON/Markdown Exporte
  evidence/                 # Quellen-Snippets und Tabellen
  embeddings/               # optional lokale Embedding-Artefakte
  notes/                    # manuelle Notizen
```

Beispiele:

```text
research/cards/PLTR_2026-05-15.md
research/frameworks/rule_of_40.json
research/frameworks/moat_scoring.json
research/evidence/PLTR_2025_10K_metrics.json
research/prompts/research_agent.md
research/prompts/red_team_agent.md
```

---

## 34. API-Endpunkte fuer das Researchmodul

Diese Datei definiert auch die fachlichen API-Anforderungen. Die konkrete technische Umsetzung steht in `Infrastructure.md`.

### 34.1 Dokumente

```text
POST   /api/research/documents/upload
GET    /api/research/documents
GET    /api/research/documents/{document_id}
POST   /api/research/documents/{document_id}/process
GET    /api/research/documents/{document_id}/chunks
GET    /api/research/documents/{document_id}/summary
```

### 34.2 Frameworks

```text
GET    /api/research/frameworks
POST   /api/research/frameworks/extract/{document_id}
GET    /api/research/frameworks/{framework_id}
PUT    /api/research/frameworks/{framework_id}
```

### 34.3 Company Research

```text
POST   /api/research/companies/{ticker}/run
GET    /api/research/companies/{ticker}/card
GET    /api/research/companies/{ticker}/metrics
GET    /api/research/companies/{ticker}/score
POST   /api/research/companies/{ticker}/red-team
POST   /api/research/companies/{ticker}/handoff-to-screener
```

### 34.4 Watchlist

```text
GET    /api/research/watchlist
POST   /api/research/watchlist/{ticker}
DELETE /api/research/watchlist/{ticker}
GET    /api/research/watchlist/export
POST   /api/research/watchlist/filter-sync
```

### 34.5 News und Sentiment

```text
GET    /api/research/news/company/{ticker}
GET    /api/research/news/market
GET    /api/research/sentiment/company/{ticker}
GET    /api/research/sentiment/market
```

### 34.6 Audit

```text
GET    /api/research/audit/{job_id}
GET    /api/research/sources/{source_id}
GET    /api/research/evidence/{evidence_id}
```

---

## 35. Sicherheitsregeln

1. Das Researchmodul darf keine Broker-API importieren.
2. Es darf keine Order-Objekte erzeugen.
3. Es darf keine Live-Portfolio-Daten veraendern.
4. Es darf nur Paper-Trading-Handoffs erzeugen.
5. Jede LLM-Ausgabe wird gespeichert und auditierbar gemacht.
6. Jede Kennzahl muss reproduzierbar aus Daten berechnet werden.
7. Jede Quelle muss gespeichert werden.
8. Jede manuelle Aenderung am Score muss geloggt werden.
9. Kein Agent darf fehlende Daten durch Fantasie ersetzen.
10. Kein Agent darf eine Aktie ohne Red-Team-Pruefung als Top-Kandidat markieren.

---

## 36. Quellen und Referenzen

Diese Datei basiert auf dem internen PDF `Wachstumsaktien Bewertung_ Kennzahlen und Scoring.pdf` sowie auf ergaenzender Recherche. Wichtige externe Referenzen:

1. AQR - Quality Minus Junk Dataset: https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly
2. Asness, Frazzini, Pedersen - Quality Minus Junk: https://link.springer.com/article/10.1007/s11142-018-9470-2
3. Morningstar Economic Moat Rating: https://www.morningstar.com/stocks/morningstar-economic-moat-rating-3
4. S&P 500 Economic Moat Indices Methodology: https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-500-econ-moat-indices.pdf
5. Bessemer Venture Partners - Rule of X: https://www.bvp.com/atlas/the-rule-of-x
6. Fama and French - A Five-Factor Asset Pricing Model: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2287202
7. Novy-Marx - The Other Side of Value: https://www.nber.org/system/files/working_papers/w15940/w15940.pdf
8. George and Hwang - The 52-Week High and Momentum Investing: https://www.bauer.uh.edu/TGeorge/papers/gh4-paper.pdf
9. Damodaran - Valuing Young, Start-up and Growth Companies: https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/younggrowth.pdf
10. McKinsey - How are companies valued?: https://www.mckinsey.com/featured-insights/mckinsey-explainers/how-are-companies-valued
11. Springer - Stock-based compensation, financial analysts, and equity overvaluation: https://link.springer.com/article/10.1007/s11142-020-09541-0
12. Federal Reserve - Predicting Analysts' S&P 500 Earnings Forecast Errors and Stock Market Returns: https://www.federalreserve.gov/econres/feds/files/2024049pap.pdf
13. MSCI - Analyst Sentiment: From factor to indexation: https://www.msci.com/research-and-insights/paper/analyst-sentiment-from-factor-to-indexation
14. LSEG - Alternative Data For Extensive Financial Analysis: https://www.lseg.com/en/data-analytics/financial-data/alternative-data
15. MDPI - Economic News, Social Media Sentiments, and Stock Returns: https://www.mdpi.com/1911-8074/18/1/16
16. UCLA Anderson Review - PEAD discussion: https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/

---

## 37. Finale Plattformregel

Eine Wachstumsaktie ist fuer die Plattform nur dann interessant, wenn sie drei Huerden schafft:

1. **Research-Huerde:** Wachstum, Qualitaet, Moat, Bewertung und Risiko sind plausibel.
2. **Trading-Huerde:** Momentum, Liquiditaet, Setup und Marktregime passen.
3. **Risiko-Huerde:** Paper-Positionsgroesse, Stop, Korrelation und Journal sind kontrolliert.

Fällt eine der drei Huerden aus, gibt es keinen Paper-Trade.

Der wichtigste Satz fuer alle Agenten lautet:

> Wir suchen keine Story-Aktien. Wir suchen quellenbasiert belegbare Wachstumsthesen, die erst nach separater Markt-, Setup- und Risiko-Pruefung als Paper-Trading-Idee simuliert werden duerfen.
