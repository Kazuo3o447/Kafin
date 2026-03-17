"""
n8n_setup — Erstellt die benötigten n8n-Workflows per API

Input:  Keine (nutzt n8n REST API)
Output: Konfigurierte Workflows in n8n
Deps:   config.py, httpx
Config: .env → N8N_USER, N8N_PASSWORD
API:    n8n REST API (http://localhost:5678)
"""

import httpx
import os
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Wenn wir innerhalb von Docker sind, ist der Host-Name "n8n", wenn außerhalb dann "localhost"
N8N_URL = os.environ.get("N8N_INTERNAL_URL", "http://n8n:5678")
N8N_USER = os.getenv("N8N_USER", "admin")
N8N_PASSWORD = os.getenv("N8N_PASSWORD", "")


async def setup_workflows():
    """Erstellt alle benötigten n8n-Workflows."""

    # Falls kein Passwort gesetzt ist, kein Auth mitsenden, aber BasicAuth verlangt zumindest leere Strings
    auth = httpx.BasicAuth(N8N_USER, N8N_PASSWORD) if N8N_PASSWORD else None
    
    # Try basic auth first
    async with httpx.AsyncClient(base_url=N8N_URL, auth=auth, timeout=30.0) as client:

        # Workflow 1: News-Pipeline alle 30 Minuten
        news_workflow = {
            "name": "Kafin: News-Pipeline (30min)",
            "active": True,
            "nodes": [
                {
                    "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 30}]}},
                    "name": "Trigger: Alle 30 Minuten",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://api:8000/api/news/scan",
                        "method": "POST",
                        "options": {}
                    },
                    "name": "News-Scan ausführen",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Alle 30 Minuten": {"main": [[{"node": "News-Scan ausführen", "type": "main", "index": 0}]]}
            }
        }

        # Workflow 2: SEC-Scanner alle 10 Minuten
        sec_workflow = {
            "name": "Kafin: SEC-Scanner (10min)",
            "active": True,
            "nodes": [
                {
                    "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 10}]}},
                    "name": "Trigger: Alle 10 Minuten",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://api:8000/api/news/sec-scan",
                        "method": "POST",
                        "options": {}
                    },
                    "name": "SEC-Scan ausführen",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Alle 10 Minuten": {"main": [[{"node": "SEC-Scan ausführen", "type": "main", "index": 0}]]}
            }
        }

        # Workflow 3: Sonntags-Report um 20:00 Uhr
        sunday_workflow = {
            "name": "Kafin: Sonntags-Report",
            "active": True,
            "nodes": [
                {
                    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 20 * * 0"}]}},
                    "name": "Trigger: Sonntag 20:00",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://api:8000/api/reports/generate-sunday",
                        "method": "POST",
                        "options": {}
                    },
                    "name": "Sonntags-Report generieren",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Sonntag 20:00": {"main": [[{"node": "Sonntags-Report generieren", "type": "main", "index": 0}]]}
            }
        }

        # Workflow 4: Morning Briefing (Montag-Freitag 08:00 CET)
        morning_workflow = {
            "name": "Kafin: Morning Briefing (Mo-Fr 08:00)",
            "active": True,
            "nodes": [
                {
                    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * 1-5"}]}},
                    "name": "Trigger: Mo-Fr 08:00 CET",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/reports/generate-morning",
                        "method": "POST",
                        "options": {"timeout": 120000}
                    },
                    "name": "Morning Briefing generieren",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Mo-Fr 07:00 CET": {"main": [[{"node": "Morning Briefing generieren", "type": "main", "index": 0}]]}
            }
        }

        # Workflow 5: Post-Earnings Review Scanner (Mo-Fr 22:00 CET)
        earnings_review_workflow = {
            "name": "Kafin: Post-Earnings Review (täglich 22:00)",
            "active": True,
            "nodes": [
                {
                    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 22 * * 1-5"}]}},
                    "name": "Trigger: Mo-Fr 22:00 CET",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/reports/scan-earnings-results",
                        "method": "POST",
                        "options": {"timeout": 120000}
                    },
                    "name": "Earnings-Ergebnisse scannen",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Mo-Fr 22:00 CET": {"main": [[{"node": "Earnings-Ergebnisse scannen", "type": "main", "index": 0}]]}
            }
        }

        for wf in [news_workflow, sec_workflow, sunday_workflow, morning_workflow, earnings_review_workflow]:
            try:
                response = await client.post("/api/v1/workflows", json=wf)
                if response.status_code in (200, 201):
                    logger.info(f"n8n Workflow erstellt: {wf['name']}")
                else:
                    logger.warning(f"n8n Workflow fehlgeschlagen: {wf['name']} - {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"n8n API-Fehler: {e}")
