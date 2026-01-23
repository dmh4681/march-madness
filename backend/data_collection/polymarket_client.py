"""
Polymarket API client for college basketball markets.

Uses the Gamma API (gamma-api.polymarket.com) which provides public market data.
No authentication required.
"""

import logging
from typing import Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class PolymarketClient:
    """Client for Polymarket Gamma API."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=GAMMA_BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "march-madness-analytics/1.0"}
        )

    async def get_college_basketball_markets(self) -> list[dict]:
        """
        Fetch all college basketball markets.

        Searches multiple relevant tags since Polymarket doesn't have
        consistent tagging for college basketball.
        """
        markets = []

        # Try multiple relevant tags and search terms
        tags = [
            "college-basketball",
            "ncaa",
            "march-madness",
            "ncaa-basketball",
            "cbb",
            "ncaab",
        ]

        search_terms = [
            "NCAA",
            "March Madness",
            "college basketball",
            "Final Four",
        ]

        seen_ids = set()

        # Search by tags
        for tag in tags:
            try:
                response = await self.client.get(
                    "/markets",
                    params={
                        "tag": tag,
                        "closed": "false",
                        "limit": 100
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    batch = data if isinstance(data, list) else data.get("markets", [])

                    for m in batch:
                        market_id = str(m.get("id", ""))
                        if market_id and market_id not in seen_ids:
                            seen_ids.add(market_id)
                            markets.append(m)

            except Exception as e:
                logger.warning(f"Error fetching Polymarket tag '{tag}': {e}")
                continue

        # Search by keywords
        for term in search_terms:
            try:
                response = await self.client.get(
                    "/markets",
                    params={
                        "search": term,
                        "closed": "false",
                        "limit": 50
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    batch = data if isinstance(data, list) else data.get("markets", [])

                    for m in batch:
                        market_id = str(m.get("id", ""))
                        # Filter to only basketball-related
                        title = m.get("question", "") or m.get("title", "")
                        title_lower = title.lower()

                        is_basketball = any(x in title_lower for x in [
                            "basketball", "ncaa", "march madness", "final four",
                            "tournament", "elite eight", "sweet sixteen"
                        ])

                        if market_id and market_id not in seen_ids and is_basketball:
                            seen_ids.add(market_id)
                            markets.append(m)

            except Exception as e:
                logger.warning(f"Error searching Polymarket for '{term}': {e}")
                continue

        logger.info(f"Polymarket: Found {len(markets)} college basketball markets")
        return markets

    async def get_market(self, market_id: str) -> Optional[dict]:
        """Fetch single market by ID."""
        try:
            response = await self.client.get(f"/markets/{market_id}")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching Polymarket market {market_id}: {e}")
        return None

    def parse_market(self, raw: dict) -> dict:
        """
        Parse Polymarket response into standard format.

        Args:
            raw: Raw market data from Polymarket API

        Returns:
            Standardized market dict matching our schema
        """
        outcomes = []

        # Polymarket uses various structures for outcomes
        raw_outcomes = raw.get("outcomes", []) or raw.get("outcomePrices", [])

        if isinstance(raw_outcomes, list):
            for i, outcome in enumerate(raw_outcomes):
                if isinstance(outcome, dict):
                    outcomes.append({
                        "name": outcome.get("name") or outcome.get("outcome") or f"Outcome {i+1}",
                        "price": float(outcome.get("price", 0) or 0),
                        "volume": float(outcome.get("volume", 0) or 0)
                    })
                elif isinstance(outcome, (int, float, str)):
                    # Just prices, need to get names separately
                    name = f"Outcome {i+1}"
                    if i == 0:
                        name = "Yes"
                    elif i == 1:
                        name = "No"
                    outcomes.append({
                        "name": name,
                        "price": float(outcome),
                        "volume": 0
                    })

        # If no outcomes parsed, try other fields
        if not outcomes:
            # Some markets have outcomePrices as comma-separated string
            prices_str = raw.get("outcomePrices", "")
            if isinstance(prices_str, str) and "," in prices_str:
                try:
                    prices = [float(p) for p in prices_str.split(",")]
                    for i, price in enumerate(prices):
                        outcomes.append({
                            "name": "Yes" if i == 0 else "No",
                            "price": price,
                            "volume": 0
                        })
                except ValueError:
                    pass

        # Determine market type from title
        title = raw.get("question", "") or raw.get("title", "")
        title_lower = title.lower()

        market_type = "futures"
        if any(x in title_lower for x in ["vs", "versus", "beat", "win game", "defeat"]):
            market_type = "game"
        elif any(x in title_lower for x in ["points", "score", "total", "over", "under"]):
            market_type = "prop"
        elif any(x in title_lower for x in ["champion", "win tournament", "final four", "win ncaa"]):
            market_type = "futures"

        # Parse end date
        end_date = None
        end_date_str = raw.get("endDate") or raw.get("end_date_iso")
        if end_date_str:
            try:
                if isinstance(end_date_str, str):
                    end_date = end_date_str
            except Exception:
                pass

        return {
            "source": "polymarket",
            "market_id": str(raw.get("id", "")),
            "title": title,
            "description": raw.get("description"),
            "market_type": market_type,
            "outcomes": outcomes,
            "status": "closed" if raw.get("closed") else "open",
            "volume": float(raw.get("volume", 0) or 0),
            "liquidity": float(raw.get("liquidity", 0) or 0),
            "end_date": end_date,
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def test_polymarket():
    """Test the Polymarket client."""
    client = PolymarketClient()
    try:
        markets = await client.get_college_basketball_markets()
        print(f"\nFound {len(markets)} markets")

        for m in markets[:5]:
            parsed = client.parse_market(m)
            print(f"\n{parsed['title']}")
            print(f"  Type: {parsed['market_type']}")
            print(f"  Outcomes: {parsed['outcomes']}")

    finally:
        await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_polymarket())
