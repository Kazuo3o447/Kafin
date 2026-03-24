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

        # Workflow 1a: News-Pipeline Werktags (Mo-Fr 13:00-22:30 CET, alle 30 Minuten)
        weekday_news_workflow = {
            "name": "Kafin: News-Pipeline Werktags (30min)",
            "active": True,
            "nodes": [
                {
                    "parameters": {
                        "rule": {
                            "interval": [
                                {"field": "cronExpression", "expression": "*/30 13-22 * * 1-5"}
                            ]
                        }
                    },
                    "name": "Trigger: Mo-Fr 13:00-22:30 CET alle 30min",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/news/scan",
                        "method": "POST",
                        "options": {"timeout": 120000}
                    },
                    "name": "News-Scan (Werktag)",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Mo-Fr 13:00-22:30 CET alle 30min": {"main": [[{"node": "News-Scan (Werktag)", "type": "main", "index": 0}]]}
            }
        }

        # Workflow 1b: News-Pipeline Wochenende (Sa-So 10/14/18/22 CET — nur Google News)
        weekend_news_workflow = {
            "name": "Kafin: News-Pipeline Wochenende (Google News)",
            "active": True,
            "nodes": [
                {
                    "parameters": {
                        "rule": {
                            "interval": [
                                {"field": "cronExpression", "expression": "0 10,14,18,22 * * 0,6"}
                            ]
                        }
                    },
                    "name": "Trigger: Wochenende alle 4h",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/news/scan-weekend",
                        "method": "POST",
                        "options": {"timeout": 60000}
                    },
                    "name": "Weekend Google News Scan",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Wochenende alle 4h": {"main": [[{"node": "Weekend Google News Scan", "type": "main", "index": 0}]]}
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
                        "url": "http://kafin-backend:8000/api/news/sec-scan",
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

        # Workflow 3: Sonntags-Report um 19:00 Uhr
        sunday_workflow = {
            "name": "Kafin: Sonntags-Report",
            "active": True,
            "nodes": [
                {
                    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 19 * * 0"}]}},
                    "name": "Trigger: Sonntag 19:00",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/reports/generate-sunday",
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
                "Trigger: Sonntag 19:00": {"main": [[{"node": "Sonntags-Report generieren", "type": "main", "index": 0}]]}
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
                "Trigger: Mo-Fr 08:00 CET": {"main": [[{"node": "Morning Briefing generieren", "type": "main", "index": 0}]]}
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

        # Workflow 6: Sentiment Divergence Monitor (stündlich Mo-Fr)
        sentiment_workflow = {
            "name": "Kafin: Sentiment Monitor (stündlich)",
            "active": True,
            "nodes": [
                {
                    "parameters": {
                        "rule": {
                            "interval": [{
                                "field": "cronExpression",
                                "expression": "0 * * * 1-5"
                            }]
                        }
                    },
                    "name": "Trigger: Stündlich Mo-Fr",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1,
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/web-intelligence/sentiment-check",
                        "method": "POST",
                        "options": {"timeout": 60000},
                    },
                    "name": "Sentiment Divergenz prüfen",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1,
                },
            ],
            "connections": {
                "Trigger: Stündlich Mo-Fr": {
                    "main": [[{
                        "node": "Sentiment Divergenz prüfen",
                        "type": "main",
                        "index": 0,
                    }]]
                }
            },
        }

        # Workflow 7: Peer Earnings Check (08:00 + 15:00 Mo-Fr)
        peer_morning_workflow = {
            "name": "Kafin: Peer Earnings Check (08:00 + 15:00)",
            "active": True,
            "nodes": [
                {
                    "parameters": {
                        "rule": {
                            "interval": [{
                                "field": "cronExpression",
                                "expression": "0 8,15 * * 1-5"
                            }]
                        }
                    },
                    "name": "Trigger: Mo-Fr 08:00 + 15:00",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1,
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/web-intelligence/peer-check",
                        "method": "POST",
                        "options": {"timeout": 30000},
                    },
                    "name": "Peer Earnings prüfen",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1,
                },
            ],
            "connections": {
                "Trigger: Mo-Fr 08:00 + 15:00": {
                    "main": [[{
                        "node": "Peer Earnings prüfen",
                        "type": "main",
                        "index": 0,
                    }]]
                }
            },
        }

        # Workflow 8: Nightly DB Backup (täglich 03:00)
        backup_workflow = {
            "name": "Kafin: Nightly DB Backup (täglich 03:00)",
            "active": True,
            "nodes": [
                {
                    "parameters": {
                        "rule": {
                            "interval": [{
                                "field": "cronExpression",
                                "expression": "0 3 * * *"
                            }]
                        }
                    },
                    "name": "Trigger: Täglich 03:00",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/admin/backup-database",
                        "method": "POST",
                        "options": {}
                    },
                    "name": "PostgreSQL Backup",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "values": {
                            "string": [{
                                "name": "log",
                                "value": "={{$json.success ? 'Backup OK: ' + $json.file : 'Backup FEHLER: ' + $json.error}}"
                            }]
                        }
                    },
                    "name": "Log Result",
                    "type": "n8n-nodes-base.set",
                    "position": [650, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Täglich 03:00": {"main": [[{"node": "PostgreSQL Backup", "type": "main", "index": 0}]]},
                "PostgreSQL Backup": {"main": [[{"node": "Log Result", "type": "main", "index": 0}]]}
            }
        }

        # Workflow 9: Earnings Auto-Trigger (täglich 08:10 Mo-Fr)
        earnings_auto_trigger_workflow = {
            "name": "Kafin: Earnings Auto-Trigger (täglich 08:10)",
            "active": True,
            "nodes": [
                {
                    "parameters": {
                        "rule": {
                            "interval": [{
                                "field": "cronExpression",
                                "expression": "10 8 * * 1-5"
                            }]
                        }
                    },
                    "name": "Trigger: Mo-Fr 08:10 CET",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "url": "http://kafin-backend:8000/api/reports/trigger-earnings-audits",
                        "method": "POST",
                        "options": {"timeout": 300000}  # 5 Min — mehrere Ticker
                    },
                    "name": "Earnings Audits triggern",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [450, 300],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Trigger: Mo-Fr 08:10 CET": {
                    "main": [[{
                        "node": "Earnings Audits triggern",
                        "type": "main",
                        "index": 0
                    }]]
                }
            }
        }

        for wf in [weekday_news_workflow, weekend_news_workflow, sec_workflow, sunday_workflow, morning_workflow, earnings_review_workflow, sentiment_workflow, peer_morning_workflow, backup_workflow, earnings_auto_trigger_workflow]:
            try:
                response = await client.post("/api/v1/workflows", json=wf)
                if response.status_code in (200, 201):
                    logger.info(f"n8n Workflow erstellt: {wf['name']}")
                else:
                    logger.warning(f"n8n Workflow fehlgeschlagen: {wf['name']} - {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"n8n API-Fehler: {e}")
