"""
Multi-source sentiment analysis: Twitter (Grok), Reddit, and News.

This module provides sentiment analysis for March Madness teams by aggregating
data from Twitter/X (via Grok API), Reddit, and News sources.

Usage:
    from backend.data_collection.sentiment_scraper import aggregate_sentiment

    sentiment = await aggregate_sentiment("Duke", opponent="UNC")
"""

import os
import re
import logging
import asyncio
from datetime import datetime, date
from typing import Optional

import praw
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# API Configuration
# =============================================================================

# Grok for Twitter sentiment (native X access)
GROK_API_KEY = os.getenv("GROK_API_KEY")
grok_client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1") if GROK_API_KEY else None

# Reddit API credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "MarchMadnessSentiment/1.0")

# NewsAPI for news sentiment
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Initialize Reddit client
reddit_client = None
if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
    try:
        reddit_client = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize Reddit client: {e}")

# Sentiment thresholds
BULLISH_THRESHOLD = 0.6
BEARISH_THRESHOLD = 0.4


def _get_sentiment_label(score: float) -> str:
    """Convert sentiment score to label."""
    if score >= BULLISH_THRESHOLD:
        return "Bullish"
    elif score <= BEARISH_THRESHOLD:
        return "Bearish"
    return "Neutral"


def _sanitize_team_name(team_name: str) -> str:
    """Sanitize team name for API queries."""
    if not team_name:
        return ""
    # Remove special characters, limit length
    sanitized = re.sub(r'[^\w\s-]', '', team_name)
    return sanitized[:100].strip()


async def analyze_twitter_sentiment(team_name: str, opponent: str = None) -> dict:
    """
    Use Grok for Twitter/X sentiment analysis.

    Grok has native access to X/Twitter data and can analyze real-time sentiment.

    Args:
        team_name: The team to analyze
        opponent: Optional opponent for matchup-specific sentiment

    Returns:
        Dict with sentiment metrics:
        - sentiment_score: 0.0-1.0 (0=very negative, 1=very positive)
        - positive_pct: Percentage of positive mentions
        - negative_pct: Percentage of negative mentions
        - neutral_pct: Percentage of neutral mentions
        - volume: low/medium/high
        - trending: Whether the team is trending
        - key_narratives: List of key talking points
        - betting_insights: Betting-related insights
        - sample_tweets: Sample tweets for context
    """
    if not grok_client:
        logger.warning("Grok client not configured, skipping Twitter sentiment")
        return _empty_sentiment_result("twitter", "Grok API key not configured")

    team_name = _sanitize_team_name(team_name)
    opponent = _sanitize_team_name(opponent) if opponent else None

    matchup_context = f" vs {opponent}" if opponent else ""

    prompt = f"""Analyze current Twitter/X sentiment for {team_name} basketball{matchup_context}.

Focus on:
1. Overall fan sentiment (confidence, excitement, concern)
2. Betting-related discussions (spreads, money lines, predictions)
3. Key narratives (injuries, momentum, matchup advantages)
4. Volume of discussion (is this game generating buzz?)

Respond in JSON format:
{{
    "sentiment_score": <float 0.0-1.0, where 0.5 is neutral>,
    "positive_pct": <float 0-100>,
    "negative_pct": <float 0-100>,
    "neutral_pct": <float 0-100>,
    "volume": "low" | "medium" | "high",
    "trending": <boolean>,
    "key_narratives": [<list of 2-4 key talking points>],
    "betting_insights": [<list of 1-3 betting-related observations>],
    "sample_tweets": [<list of 2-3 representative tweet summaries>]
}}

Respond with ONLY the JSON object."""

    try:
        response = grok_client.chat.completions.create(
            model="grok-3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )

        response_text = response.choices[0].message.content

        # Parse JSON from response
        result = _extract_json_from_response(response_text)
        result["source"] = "twitter"
        result["captured_at"] = datetime.utcnow().isoformat()

        return result

    except Exception as e:
        logger.error(f"Error analyzing Twitter sentiment: {e}")
        return _empty_sentiment_result("twitter", str(e))


async def analyze_reddit_sentiment(team_name: str) -> dict:
    """
    Scrape r/CollegeBasketball and team-specific subreddits for sentiment.

    Args:
        team_name: The team to analyze

    Returns:
        Dict with sentiment metrics similar to Twitter analysis
    """
    if not reddit_client:
        logger.warning("Reddit client not configured, skipping Reddit sentiment")
        return _empty_sentiment_result("reddit", "Reddit API credentials not configured")

    team_name = _sanitize_team_name(team_name)

    try:
        posts = []
        comments_text = []

        # Search r/CollegeBasketball for team mentions
        subreddit = reddit_client.subreddit("CollegeBasketball")

        # Get recent posts mentioning the team
        for submission in subreddit.search(team_name, sort="new", time_filter="week", limit=25):
            posts.append({
                "title": submission.title,
                "score": submission.score,
                "num_comments": submission.num_comments,
                "upvote_ratio": submission.upvote_ratio,
            })

            # Get top comments from each post
            submission.comments.replace_more(limit=0)
            for comment in submission.comments[:5]:
                if hasattr(comment, 'body'):
                    comments_text.append(comment.body[:500])

        # Calculate sentiment based on engagement metrics
        if not posts:
            return _empty_sentiment_result("reddit", "No recent posts found")

        # Calculate metrics
        total_score = sum(p["score"] for p in posts)
        total_comments = sum(p["num_comments"] for p in posts)
        avg_upvote_ratio = sum(p["upvote_ratio"] for p in posts) / len(posts)

        # Determine volume
        if len(posts) >= 20:
            volume = "high"
        elif len(posts) >= 10:
            volume = "medium"
        else:
            volume = "low"

        # Estimate sentiment from upvote ratios (>0.7 = positive discussion)
        positive_posts = sum(1 for p in posts if p["upvote_ratio"] > 0.7)
        negative_posts = sum(1 for p in posts if p["upvote_ratio"] < 0.5)
        neutral_posts = len(posts) - positive_posts - negative_posts

        positive_pct = (positive_posts / len(posts)) * 100
        negative_pct = (negative_posts / len(posts)) * 100
        neutral_pct = (neutral_posts / len(posts)) * 100

        # Calculate overall sentiment score
        sentiment_score = 0.5 + (avg_upvote_ratio - 0.5) * 0.5
        sentiment_score = max(0.0, min(1.0, sentiment_score))

        # Extract key narratives from post titles
        key_narratives = [p["title"][:100] for p in sorted(posts, key=lambda x: x["score"], reverse=True)[:3]]

        return {
            "source": "reddit",
            "sentiment_score": round(sentiment_score, 3),
            "positive_pct": round(positive_pct, 2),
            "negative_pct": round(negative_pct, 2),
            "neutral_pct": round(neutral_pct, 2),
            "volume": volume,
            "trending": total_comments > 500,
            "key_narratives": key_narratives,
            "betting_insights": [],  # Reddit doesn't have specific betting insights from API
            "sample_tweets": [],  # Not applicable for Reddit
            "post_count": len(posts),
            "total_engagement": total_score + total_comments,
            "captured_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error analyzing Reddit sentiment: {e}")
        return _empty_sentiment_result("reddit", str(e))


async def analyze_news_sentiment(team_name: str) -> dict:
    """
    Fetch sports news via NewsAPI and analyze sentiment.

    Args:
        team_name: The team to analyze

    Returns:
        Dict with sentiment metrics based on news articles
    """
    if not NEWS_API_KEY:
        logger.warning("NewsAPI key not configured, skipping news sentiment")
        return _empty_sentiment_result("news", "NewsAPI key not configured")

    team_name = _sanitize_team_name(team_name)

    try:
        # Build search query
        query = f'"{team_name}" basketball'

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "apiKey": NEWS_API_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "domains": "espn.com,cbssports.com,bleacherreport.com,sports.yahoo.com,theathletic.com",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        articles = data.get("articles", [])

        if not articles:
            return _empty_sentiment_result("news", "No recent news articles found")

        # Analyze headlines for sentiment keywords
        positive_keywords = [
            "win", "winning", "dominant", "surge", "upset", "strong", "confident",
            "momentum", "hot", "streak", "championship", "favorite", "elite"
        ]
        negative_keywords = [
            "loss", "lose", "struggle", "injury", "injured", "doubt", "concern",
            "slump", "cold", "weak", "underdog", "worry", "upset"
        ]

        positive_count = 0
        negative_count = 0
        headlines = []

        for article in articles:
            title = (article.get("title") or "").lower()
            description = (article.get("description") or "").lower()
            text = f"{title} {description}"

            headlines.append(article.get("title", "")[:100])

            pos_matches = sum(1 for kw in positive_keywords if kw in text)
            neg_matches = sum(1 for kw in negative_keywords if kw in text)

            if pos_matches > neg_matches:
                positive_count += 1
            elif neg_matches > pos_matches:
                negative_count += 1

        total = len(articles)
        neutral_count = total - positive_count - negative_count

        positive_pct = (positive_count / total) * 100
        negative_pct = (negative_count / total) * 100
        neutral_pct = (neutral_count / total) * 100

        # Calculate sentiment score
        sentiment_score = 0.5 + ((positive_count - negative_count) / total) * 0.4
        sentiment_score = max(0.0, min(1.0, sentiment_score))

        # Determine volume based on article count
        if total >= 15:
            volume = "high"
        elif total >= 7:
            volume = "medium"
        else:
            volume = "low"

        return {
            "source": "news",
            "sentiment_score": round(sentiment_score, 3),
            "positive_pct": round(positive_pct, 2),
            "negative_pct": round(negative_pct, 2),
            "neutral_pct": round(neutral_pct, 2),
            "volume": volume,
            "trending": total >= 15,
            "key_narratives": headlines[:3],
            "betting_insights": [],
            "sample_tweets": [],
            "article_count": total,
            "captured_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error analyzing news sentiment: {e}")
        return _empty_sentiment_result("news", str(e))


async def aggregate_sentiment(team_name: str, opponent: str = None) -> dict:
    """
    Combine sentiment from all sources: Twitter 50%, Reddit 30%, News 20%.

    Args:
        team_name: The team to analyze
        opponent: Optional opponent for matchup-specific analysis

    Returns:
        Aggregated sentiment dict with weighted scores and combined insights
    """
    # Fetch sentiment from all sources concurrently
    twitter_task = analyze_twitter_sentiment(team_name, opponent)
    reddit_task = analyze_reddit_sentiment(team_name)
    news_task = analyze_news_sentiment(team_name)

    twitter_sentiment, reddit_sentiment, news_sentiment = await asyncio.gather(
        twitter_task, reddit_task, news_task
    )

    # Weight configuration
    weights = {
        "twitter": 0.50,
        "reddit": 0.30,
        "news": 0.20,
    }

    # Collect valid sources
    sources = []
    if twitter_sentiment.get("sentiment_score") is not None and not twitter_sentiment.get("error"):
        sources.append(("twitter", twitter_sentiment))
    if reddit_sentiment.get("sentiment_score") is not None and not reddit_sentiment.get("error"):
        sources.append(("reddit", reddit_sentiment))
    if news_sentiment.get("sentiment_score") is not None and not news_sentiment.get("error"):
        sources.append(("news", news_sentiment))

    if not sources:
        return {
            "team_name": team_name,
            "opponent": opponent,
            "sentiment_score": None,
            "positive_pct": None,
            "negative_pct": None,
            "neutral_pct": None,
            "volume": "unknown",
            "trending": False,
            "key_narratives": [],
            "betting_insights": [],
            "sample_tweets": [],
            "confidence": 0.0,
            "source": "aggregated",
            "sources_used": [],
            "error": "No sentiment sources available",
            "captured_at": datetime.utcnow().isoformat(),
            "captured_date": date.today().isoformat(),
        }

    # Normalize weights based on available sources
    total_weight = sum(weights[name] for name, _ in sources)
    normalized_weights = {name: weights[name] / total_weight for name, _ in sources}

    # Calculate weighted averages
    weighted_sentiment = 0.0
    weighted_positive = 0.0
    weighted_negative = 0.0
    weighted_neutral = 0.0

    for name, data in sources:
        w = normalized_weights[name]
        weighted_sentiment += data.get("sentiment_score", 0.5) * w
        weighted_positive += data.get("positive_pct", 33.33) * w
        weighted_negative += data.get("negative_pct", 33.33) * w
        weighted_neutral += data.get("neutral_pct", 33.33) * w

    # Aggregate volume (take highest)
    volume_priority = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
    volumes = [data.get("volume", "unknown") for _, data in sources]
    aggregated_volume = max(volumes, key=lambda v: volume_priority.get(v, 0))

    # Aggregate trending (any trending = trending)
    trending = any(data.get("trending", False) for _, data in sources)

    # Combine narratives and insights
    all_narratives = []
    all_insights = []
    sample_tweets = []

    for _, data in sources:
        all_narratives.extend(data.get("key_narratives", [])[:2])
        all_insights.extend(data.get("betting_insights", [])[:2])
        sample_tweets.extend(data.get("sample_tweets", [])[:2])

    # Dedupe and limit
    key_narratives = list(dict.fromkeys(all_narratives))[:5]
    betting_insights = list(dict.fromkeys(all_insights))[:3]
    sample_tweets = sample_tweets[:3]

    # Calculate confidence based on number of sources and their quality
    confidence = len(sources) / 3.0

    return {
        "team_name": team_name,
        "opponent": opponent,
        "sentiment_score": round(weighted_sentiment, 3),
        "sentiment_label": _get_sentiment_label(weighted_sentiment),
        "positive_pct": round(weighted_positive, 2),
        "negative_pct": round(weighted_negative, 2),
        "neutral_pct": round(weighted_neutral, 2),
        "volume": aggregated_volume,
        "trending": trending,
        "key_narratives": key_narratives,
        "betting_insights": betting_insights,
        "sample_tweets": sample_tweets,
        "confidence": round(confidence, 3),
        "source": "aggregated",
        "sources_used": [name for name, _ in sources],
        "source_details": {
            "twitter": twitter_sentiment,
            "reddit": reddit_sentiment,
            "news": news_sentiment,
        },
        "captured_at": datetime.utcnow().isoformat(),
        "captured_date": date.today().isoformat(),
    }


def _empty_sentiment_result(source: str, error: str = None) -> dict:
    """Create an empty sentiment result for when a source is unavailable."""
    return {
        "source": source,
        "sentiment_score": None,
        "positive_pct": None,
        "negative_pct": None,
        "neutral_pct": None,
        "volume": "unknown",
        "trending": False,
        "key_narratives": [],
        "betting_insights": [],
        "sample_tweets": [],
        "error": error,
        "captured_at": datetime.utcnow().isoformat(),
    }


def _extract_json_from_response(response_text: str) -> dict:
    """Extract JSON from AI response text."""
    import json

    # Try direct parse
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Look for JSON code blocks
    json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Find outermost JSON object
    start_idx = response_text.find('{')
    if start_idx != -1:
        brace_count = 0
        end_idx = start_idx

        for i, char in enumerate(response_text[start_idx:], start=start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        if brace_count == 0:
            json_str = response_text[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    # Return defaults
    return {
        "sentiment_score": 0.5,
        "positive_pct": 33.33,
        "negative_pct": 33.33,
        "neutral_pct": 33.34,
        "volume": "unknown",
        "trending": False,
        "key_narratives": ["Unable to parse sentiment response"],
        "betting_insights": [],
        "sample_tweets": [],
    }


async def refresh_sentiment_for_games(game_ids: list[str] = None) -> dict:
    """
    Refresh sentiment data for today's games.

    Args:
        game_ids: Optional list of specific game IDs to refresh. If None, refreshes all today's games.

    Returns:
        Summary of refresh results
    """
    from backend.api.supabase_client import (
        get_supabase,
        get_games_by_date,
        get_eastern_date_today,
    )

    print("\n=== Refreshing Sentiment Data ===")

    client = get_supabase()
    today = get_eastern_date_today()

    # Get games to analyze
    if game_ids:
        # Specific games
        games = []
        for gid in game_ids:
            result = client.table("games").select(
                "id, home_team:teams!games_home_team_id_fkey(id, name), "
                "away_team:teams!games_away_team_id_fkey(id, name)"
            ).eq("id", gid).execute()
            if result.data:
                games.extend(result.data)
    else:
        # Today's games
        result = client.table("games").select(
            "id, home_team:teams!games_home_team_id_fkey(id, name), "
            "away_team:teams!games_away_team_id_fkey(id, name)"
        ).eq("date", today.isoformat()).execute()
        games = result.data or []

    if not games:
        print("No games found to analyze sentiment for")
        return {"status": "no_games", "sentiments_created": 0}

    print(f"Analyzing sentiment for {len(games)} games ({len(games) * 2} teams)")

    sentiments_created = 0
    errors = 0

    for game in games:
        game_id = game["id"]
        home_team = game.get("home_team", {})
        away_team = game.get("away_team", {})

        home_name = home_team.get("name", "Unknown")
        away_name = away_team.get("name", "Unknown")
        home_team_id = home_team.get("id")
        away_team_id = away_team.get("id")

        # Analyze home team sentiment
        try:
            print(f"  Analyzing {home_name}...")
            home_sentiment = await aggregate_sentiment(home_name, opponent=away_name)

            if home_sentiment.get("sentiment_score") is not None:
                # Store in database
                sentiment_data = {
                    "team_id": home_team_id,
                    "game_id": game_id,
                    "season": 2025,
                    "sentiment_score": home_sentiment.get("sentiment_score"),
                    "positive_pct": home_sentiment.get("positive_pct"),
                    "negative_pct": home_sentiment.get("negative_pct"),
                    "neutral_pct": home_sentiment.get("neutral_pct"),
                    "volume": home_sentiment.get("volume"),
                    "trending": home_sentiment.get("trending", False),
                    "key_narratives": home_sentiment.get("key_narratives", []),
                    "betting_insights": home_sentiment.get("betting_insights", []),
                    "sample_tweets": home_sentiment.get("sample_tweets", []),
                    "confidence": home_sentiment.get("confidence"),
                    "source": "aggregated",
                }

                client.table("sentiment_ratings").upsert(
                    sentiment_data,
                    on_conflict="team_id,game_id,captured_date"
                ).execute()
                sentiments_created += 1
                print(f"    -> Score: {home_sentiment.get('sentiment_score'):.3f} ({home_sentiment.get('sentiment_label', 'N/A')})")

        except Exception as e:
            errors += 1
            print(f"    Error analyzing {home_name}: {e}")

        # Analyze away team sentiment
        try:
            print(f"  Analyzing {away_name}...")
            away_sentiment = await aggregate_sentiment(away_name, opponent=home_name)

            if away_sentiment.get("sentiment_score") is not None:
                sentiment_data = {
                    "team_id": away_team_id,
                    "game_id": game_id,
                    "season": 2025,
                    "sentiment_score": away_sentiment.get("sentiment_score"),
                    "positive_pct": away_sentiment.get("positive_pct"),
                    "negative_pct": away_sentiment.get("negative_pct"),
                    "neutral_pct": away_sentiment.get("neutral_pct"),
                    "volume": away_sentiment.get("volume"),
                    "trending": away_sentiment.get("trending", False),
                    "key_narratives": away_sentiment.get("key_narratives", []),
                    "betting_insights": away_sentiment.get("betting_insights", []),
                    "sample_tweets": away_sentiment.get("sample_tweets", []),
                    "confidence": away_sentiment.get("confidence"),
                    "source": "aggregated",
                }

                client.table("sentiment_ratings").upsert(
                    sentiment_data,
                    on_conflict="team_id,game_id,captured_date"
                ).execute()
                sentiments_created += 1
                print(f"    -> Score: {away_sentiment.get('sentiment_score'):.3f} ({away_sentiment.get('sentiment_label', 'N/A')})")

        except Exception as e:
            errors += 1
            print(f"    Error analyzing {away_name}: {e}")

        # Rate limiting - be nice to APIs
        await asyncio.sleep(1)

    print(f"\nSentiment refresh complete: {sentiments_created} created, {errors} errors")

    return {
        "status": "success",
        "sentiments_created": sentiments_created,
        "errors": errors,
        "games_analyzed": len(games),
    }


if __name__ == "__main__":
    import asyncio

    async def main():
        # Test with a sample team
        result = await aggregate_sentiment("Duke", opponent="UNC")
        print("\n=== Aggregated Sentiment ===")
        print(f"Team: {result.get('team_name')}")
        print(f"Score: {result.get('sentiment_score')} ({result.get('sentiment_label')})")
        print(f"Breakdown: +{result.get('positive_pct')}% / -{result.get('negative_pct')}% / ~{result.get('neutral_pct')}%")
        print(f"Volume: {result.get('volume')} {'(TRENDING)' if result.get('trending') else ''}")
        print(f"Narratives: {result.get('key_narratives')}")
        print(f"Betting Insights: {result.get('betting_insights')}")
        print(f"Confidence: {result.get('confidence')}")
        print(f"Sources: {result.get('sources_used')}")

    asyncio.run(main())
