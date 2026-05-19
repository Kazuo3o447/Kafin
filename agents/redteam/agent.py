from __future__ import annotations

from agents.redteam.schema import RedTeamReport
from agents.research.schema import ResearchCard


class RedTeamAgent:
    def run(self, card: ResearchCard) -> RedTeamReport:
        weak_evidence = []
        if card.moat_assessment.get("rating") in {"Unknown", "No Moat", None}:
            weak_evidence.append("Moat ist nicht quellenbasiert belegt.")
        if not card.source_list:
            weak_evidence.append("Quellenliste fehlt oder ist leer.")
        if not card.catalysts:
            weak_evidence.append("Katalysatoren und Revisionen sind nicht belegt.")

        disqualifiers = list(card.hard_blockers)
        recommendation = "reject" if disqualifiers else "revise"
        if not disqualifiers and card.growth_research_score >= 70:
            recommendation = "revise"
        if not disqualifiers and card.growth_research_score < 50:
            recommendation = "too_hard"

        return RedTeamReport(
            ticker=card.ticker,
            weakest_assumptions=[
                "Die Score-Komponenten koennen noch nicht sector-relative validiert sein.",
                "Der qualitative Moat ist im Scaffold nicht durch Filings oder Calls falsifiziert.",
                "Bewertung kann ohne Peer- und historische Bandbreite zu optimistisch wirken.",
            ],
            disqualifiers=disqualifiers,
            weak_evidence=weak_evidence,
            recommendation=recommendation,
        )
