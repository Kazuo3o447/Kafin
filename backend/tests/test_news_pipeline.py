import pytest
from unittest.mock import patch, MagicMock
from backend.app.data.news_processor import _categorize_news, process_news_for_ticker
from backend.app.data.sec_edgar import check_recent_filings
from typing import Any  

class NewsItem:
    def __init__(self, headline: str, summary: str, source: str):
        self.headline = headline
        self.summary = summary
        self.source = source

@pytest.fixture
def mock_news():
    return [
        NewsItem("Apple reports record earnings for Q4", "EPS beats expectations", "Finnhub"),
        NewsItem("SEC investigates new accounting practices", "Regulatory scrutiny increases", "Yahoo"),
        NewsItem("New iPhone launched", "General product update", "Finnhub")
    ]

def test_categorize_news():
    assert _categorize_news("Apple reports record earnings", "EPS beat") == "earnings"
    assert _categorize_news("SEC investigates startup", "Subpoena issued") == "regulatory"
    assert _categorize_news("CEO resigns unexpectedly", "Board looking for replacement") == "management"
    assert _categorize_news("Just a normal day", "Nothing special") == "general"

@pytest.mark.asyncio
@patch("backend.app.data.news_processor.get_company_news")
@patch("backend.app.data.news_processor.get_existing_urls")
@patch("backend.app.data.news_processor.analyze_sentiment_batch")
@patch("backend.app.data.news_processor.save_bullet_points")
@patch("backend.app.data.news_processor._extract_bullet_points")
@patch("backend.app.data.news_processor.send_telegram_alert")
async def test_process_news_for_ticker(mock_alert, mock_extract, mock_save, mock_sentiment, mock_urls, mock_news_api, mock_news):
    # Setup mocks
    mock_news_api.return_value = mock_news
    mock_urls.return_value = set() # No duplicates
    mock_sentiment.return_value = [0.8, -0.9, 0.1] # Positive (Earnings), Very Negative (SEC), Neutral (Product)
    
    mock_extract.return_value = ["Point 1"]
    
    # Run
    stats = await process_news_for_ticker("AAPL")
    
    # The neutral news (0.1) should be filtered out. The other two (0.8 and -0.9) pass.
    assert stats["total_fetched"] == 3
    assert stats["passed_finbert"] == 2
    assert stats["bullets_saved"] == 2
    
    # We should have 1 alert for the very negative news (< -0.5)
    assert mock_alert.call_count == 1
    assert mock_save.call_count == 2


@pytest.mark.asyncio
@patch("backend.app.data.sec_edgar.httpx.AsyncClient.get")
async def test_sec_edgar_scanner(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "file_date": "2026-03-08",
                        "display_names": ["Form 8-K - Current report"],
                        "entity_id": "0000320193"
                    }
                }
            ]
        }
    }
    mock_get.return_value = mock_response
    
    filings = await check_recent_filings("AAPL", form_types=["8-K"])
    
    assert len(filings) == 1
    assert filings[0]["form_type"] == "8-K"
    assert filings[0]["ticker"] == "AAPL"
