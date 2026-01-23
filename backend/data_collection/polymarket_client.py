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

        Uses Polymarket's tag_id system:
        - Tag 100149: NCAAB futures (e.g., "#1 seed" markets)
        - Tag 100639: Game-specific markets (team vs team)
        """
        markets = []
        seen_ids = set()

        # NCAAB-specific tag IDs discovered from /sports endpoint
        ncaab_tag_ids = [
            "100149",  # NCAAB futures (March Madness seeding, championship)
            "100639",  # Game-specific markets
        ]

        # Fetch markets by tag_id
        for tag_id in ncaab_tag_ids:
            cursor = None
            pages_fetched = 0
            max_pages = 5  # Limit to prevent infinite loops

            while pages_fetched < max_pages:
                try:
                    params = {
                        "tag_id": tag_id,
                        "closed": "false",
                        "limit": 100
                    }
                    if cursor:
                        params["cursor"] = cursor

                    response = await self.client.get("/markets", params=params)

                    if response.status_code == 200:
                        data = response.json()
                        batch = data if isinstance(data, list) else data.get("markets", [])

                        for m in batch:
                            market_id = str(m.get("id", ""))
                            title = (m.get("question", "") or m.get("title", "")).lower()

                            # Filter to basketball-related only (tag 100639 has mixed sports)
                            is_basketball = any(x in title for x in [
                                "basketball", "ncaa", "march madness", "final four",
                                "tournament", "elite eight", "sweet sixteen",
                                # Common college basketball team names as backup
                                "duke", "kentucky", "kansas", "unc", "gonzaga",
                                "villanova", "purdue", "houston", "uconn",
                            ]) or "vs." in title or "vs " in title

                            # Tag 100149 is specifically NCAAB, trust it
                            if tag_id == "100149":
                                is_basketball = True

                            if market_id and market_id not in seen_ids and is_basketball:
                                seen_ids.add(market_id)
                                markets.append(m)

                        # Handle pagination
                        if isinstance(data, dict) and data.get("next_cursor"):
                            cursor = data["next_cursor"]
                            pages_fetched += 1
                        else:
                            break
                    else:
                        logger.warning(f"Polymarket tag {tag_id} returned {response.status_code}")
                        break

                except Exception as e:
                    logger.warning(f"Error fetching Polymarket tag_id '{tag_id}': {e}")
                    break

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

        # Polymarket returns separate arrays for outcome names and prices
        # outcomes: ["Yes", "No"] (or team names for multi-outcome)
        # outcomePrices: ["0.505", "0.495"] (string prices as decimals 0-1)
        outcome_names = raw.get("outcomes", [])
        outcome_prices = raw.get("outcomePrices", [])

        # Handle string format (JSON string arrays)
        if isinstance(outcome_names, str):
            try:
                import json
                outcome_names = json.loads(outcome_names)
            except (json.JSONDecodeError, TypeError):
                outcome_names = []

        if isinstance(outcome_prices, str):
            try:
                import json
                outcome_prices = json.loads(outcome_prices)
            except (json.JSONDecodeError, TypeError):
                outcome_prices = []

        # Combine names and prices
        if outcome_names and outcome_prices:
            for i, name in enumerate(outcome_names):
                price = 0.0
                if i < len(outcome_prices):
                    try:
                        price = float(outcome_prices[i])
                    except (ValueError, TypeError):
                        price = 0.0
                outcomes.append({
                    "name": str(name),
                    "price": price,
                    "volume": float(raw.get("volume", 0) or 0)
                })
        elif outcome_prices:
            # Only prices, use default names
            for i, price_str in enumerate(outcome_prices):
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    price = 0.0
                outcomes.append({
                    "name": "Yes" if i == 0 else "No",
                    "price": price,
                    "volume": 0
                })

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
