"""D-013: Financial Data Crawler — FireCrawl Lane 1

Scrapes earnings transcripts, analyst reports, and SEC filings into
structured signal data for the D-013 thesis pipeline.

Usage:
    python3 financial_crawler.py --ticker AAPL
    python3 financial_crawler.py --ticker AAPL --output /tmp/aapl.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "fc-d0941bd45bbf4d4dbedfa1a5701bdebe")
API_BASE = "https://api.firecrawl.dev/v1"
TIMEOUT = 30


def scrape_url(url: str) -> dict | None:
    """Scrape a URL and return the markdown content."""
    resp = requests.post(
        f"{API_BASE}/scrape",
        headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
        json={"url": url, "formats": ["markdown"]},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("success"):
        return data["data"]
    return None


def extract_earnings(ticker: str) -> dict | None:
    """Scrape the most recent earnings transcript summary."""
    urls = [
        f"https://seekingalpha.com/symbol/{ticker}/earnings",
        f"https://www.marketbeat.com/stocks/NASDAQ/{ticker}/earnings/",
    ]
    for url in urls:
        try:
            result = scrape_url(url)
            if result:
                content = result.get("markdown", "")
                if len(content) > 200:
                    return {"source": url, "content_preview": content[:3000], "scraped_at": datetime.now(timezone.utc).isoformat()}
        except Exception:
            continue
    return None


def extract_analyst_targets(ticker: str) -> dict | None:
    """Scrape analyst price targets and ratings."""
    urls = [
        f"https://www.marketbeat.com/stocks/NASDAQ/{ticker}/price-target/",
        f"https://www.tipranks.com/stocks/{ticker}/",
    ]
    for url in urls:
        try:
            result = scrape_url(url)
            if result:
                content = result.get("markdown", "")
                if len(content) > 200:
                    return {"source": url, "content_preview": content[:3000], "scraped_at": datetime.now(timezone.utc).isoformat()}
        except Exception:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description="D-013 Financial Data Crawler")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    result = {
        "ticker": ticker,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "earnings": extract_earnings(ticker),
        "analyst_targets": extract_analyst_targets(ticker),
    }

    output = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(output)
        print(f"Saved to {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
