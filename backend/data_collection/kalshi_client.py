"""
Kalshi API client with RSA-PSS-SHA256 authentication.

Kalshi requires signed requests using RSA-PSS with SHA256.
API credentials needed: KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH
"""

import os
import time
import base64
import logging
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

# College basketball related series prefixes
CBB_SERIES_PREFIXES = [
    "NCAAM",      # NCAA Men's Basketball
    "NCAAB",      # NCAA Basketball
    "CBB",        # College Basketball
    "MARCHMAD",   # March Madness
    "MM",         # March Madness abbreviated
    "FINALFOUR",  # Final Four
    "NCAAT",      # NCAA Tournament
]


class KalshiClient:
    """
    Client for Kalshi Trade API v2.

    Requires RSA-PSS-SHA256 signed requests for authentication.
    """

    def __init__(self):
        self.api_key = os.getenv("KALSHI_API_KEY")
        self.private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        self._private_key = None
        self.client = httpx.AsyncClient(
            base_url=KALSHI_BASE_URL,
            timeout=30.0
        )

    @property
    def is_configured(self) -> bool:
        """Check if Kalshi credentials are configured."""
        return bool(self.api_key and self.private_key_path)

    @property
    def private_key(self):
        """Lazy load private key from file."""
        if self._private_key is None and self.private_key_path:
            try:
                from cryptography.hazmat.primitives import serialization

                with open(self.private_key_path, "rb") as f:
                    self._private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None
                    )
                logger.info("Kalshi private key loaded successfully")
            except FileNotFoundError:
                logger.error(f"Kalshi private key file not found: {self.private_key_path}")
            except Exception as e:
                logger.error(f"Error loading Kalshi private key: {e}")

        return self._private_key

    def _sign_request(self, method: str, path: str, timestamp: str) -> str:
        """
        Generate RSA-PSS-SHA256 signature for Kalshi API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /markets)
            timestamp: Unix timestamp in milliseconds as string

        Returns:
            Base64 encoded signature
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        if not self.private_key:
            raise ValueError("Private key not loaded")

        # Message format: timestamp + method + path
        message = f"{timestamp}{method}{path}".encode()

        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return base64.b64encode(signature).decode()

    def _get_headers(self, method: str, path: str) -> dict:
        """Build authenticated headers for Kalshi API."""
        timestamp = str(int(time.time() * 1000))

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key and self.private_key:
            signature = self._sign_request(method, path, timestamp)
            headers.update({
                "KALSHI-ACCESS-KEY": self.api_key,
                "KALSHI-ACCESS-SIGNATURE": signature,
                "KALSHI-ACCESS-TIMESTAMP": timestamp,
            })

        return headers

    async def get_college_basketball_markets(self) -> list[dict]:
        """
        Fetch NCAA basketball markets from Kalshi.

        Returns markets that match college basketball series prefixes
        or contain relevant keywords in the title.
        """
        if not self.is_configured:
            logger.warning("Kalshi credentials not configured, skipping")
            return []

        markets = []
        cursor = None

        try:
            while True:
                path = "/markets"
                params = {"limit": 100, "status": "open"}
                if cursor:
                    params["cursor"] = cursor

                headers = self._get_headers("GET", path)
                response = await self.client.get(path, headers=headers, params=params)

                if response.status_code == 401:
                    logger.error("Kalshi authentication failed - check API key and private key")
                    break
                elif response.status_code != 200:
                    logger.error(f"Kalshi API error: {response.status_code} - {response.text[:200]}")
                    break

                data = response.json()
                batch = data.get("markets", [])

                # Filter for college basketball
                for m in batch:
                    ticker = m.get("ticker", "")
                    title = (m.get("title", "") or "").lower()
                    category = (m.get("category", "") or "").lower()

                    # Check ticker prefix
                    is_cbb_ticker = any(
                        ticker.upper().startswith(prefix)
                        for prefix in CBB_SERIES_PREFIXES
                    )

                    # Check keywords in title
                    is_cbb_title = any(x in title for x in [
                        "ncaa", "college basketball", "march madness",
                        "final four", "elite eight", "sweet sixteen",
                        "ncaa tournament", "national championship"
                    ])

                    # Check category
                    is_cbb_category = "basketball" in category or "ncaa" in category

                    if is_cbb_ticker or is_cbb_title or is_cbb_category:
                        markets.append(m)

                cursor = data.get("cursor")
                if not cursor or not batch:
                    break

            logger.info(f"Kalshi: Found {len(markets)} college basketball markets")

        except Exception as e:
            logger.error(f"Error fetching Kalshi markets: {e}")

        return markets

    async def get_market(self, ticker: str) -> Optional[dict]:
        """Fetch single market by ticker."""
        if not self.is_configured:
            return None

        try:
            path = f"/markets/{ticker}"
            headers = self._get_headers("GET", path)
            response = await self.client.get(path, headers=headers)

            if response.status_code == 200:
                return response.json().get("market")

        except Exception as e:
            logger.error(f"Error fetching Kalshi market {ticker}: {e}")

        return None

    def parse_market(self, raw: dict) -> dict:
        """
        Parse Kalshi response into standard format.

        Kalshi markets are typically binary (Yes/No).
        """
        # Get prices - Kalshi uses yes_ask/yes_bid or last_price
        yes_price = raw.get("yes_ask") or raw.get("last_price") or 0.5
        if isinstance(yes_price, str):
            yes_price = float(yes_price)

        # Yes price is in cents (0-100), convert to probability (0-1)
        if yes_price > 1:
            yes_price = yes_price / 100

        no_price = 1 - yes_price

        outcomes = [
            {"name": "Yes", "price": round(yes_price, 4), "volume": raw.get("volume", 0)},
            {"name": "No", "price": round(no_price, 4), "volume": raw.get("volume", 0)}
        ]

        # Determine market type from ticker/title
        ticker = raw.get("ticker", "")
        title = (raw.get("title", "") or "").lower()

        market_type = "futures"
        if "-VS-" in ticker.upper() or "vs" in title or "beat" in title:
            market_type = "game"
        elif any(x in title for x in ["points", "score", "total", "over", "under"]):
            market_type = "prop"
        elif any(x in title for x in ["champion", "win", "advance"]):
            market_type = "futures"

        return {
            "source": "kalshi",
            "market_id": raw.get("ticker"),
            "title": raw.get("title", ""),
            "description": raw.get("subtitle") or raw.get("rules_primary"),
            "market_type": market_type,
            "outcomes": outcomes,
            "status": raw.get("status", "open"),
            "volume": float(raw.get("volume", 0) or 0),
            "liquidity": float(raw.get("open_interest", 0) or 0),
            "end_date": raw.get("close_time"),
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def test_kalshi():
    """Test the Kalshi client."""
    client = KalshiClient()

    if not client.is_configured:
        print("Kalshi not configured (missing KALSHI_API_KEY or KALSHI_PRIVATE_KEY_PATH)")
        return

    try:
        markets = await client.get_college_basketball_markets()
        print(f"\nFound {len(markets)} markets")

        for m in markets[:5]:
            parsed = client.parse_market(m)
            print(f"\n{parsed['title']}")
            print(f"  Ticker: {parsed['market_id']}")
            print(f"  Type: {parsed['market_type']}")
            print(f"  Outcomes: {parsed['outcomes']}")

    finally:
        await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_kalshi())
