"""
In-Memory Cache Module

Provides a simple TTL-based cache for KenPom and Haslametrics data.
No external dependencies (Redis, etc.) - just Python dicts with expiration.

Usage:
    from backend.utils.cache import ratings_cache

    # Get cached data
    data = ratings_cache.get("kenpom", season=2025)

    # Set cached data
    ratings_cache.set("kenpom", data, season=2025)

    # Invalidate cache
    ratings_cache.invalidate("kenpom")  # Clear KenPom cache
    ratings_cache.invalidate_all()       # Clear all caches
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

# Default TTL: 1 hour
DEFAULT_TTL_SECONDS = 3600


@dataclass
class CacheEntry:
    """A single cache entry with value and expiration time."""
    value: Any
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return datetime.now() >= self.expires_at


class TTLCache:
    """
    Thread-safe TTL-based in-memory cache.

    Features:
    - Configurable TTL per cache type
    - Hit/miss logging
    - Thread-safe operations
    - Selective invalidation by key prefix
    """

    def __init__(self, default_ttl: int = DEFAULT_TTL_SECONDS):
        """
        Initialize the cache.

        Args:
            default_ttl: Default time-to-live in seconds
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "invalidations": 0,
        }
        logger.info(f"TTLCache initialized with default TTL of {default_ttl} seconds")

    def _make_key(self, prefix: str, **kwargs) -> str:
        """Create a cache key from prefix and kwargs."""
        if not kwargs:
            return prefix
        parts = [prefix] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return ":".join(str(p) for p in parts)

    def get(self, prefix: str, **kwargs) -> Optional[Any]:
        """
        Get a value from the cache.

        Args:
            prefix: Cache key prefix (e.g., "kenpom", "haslametrics")
            **kwargs: Additional key components (e.g., season=2025, team_id="...")

        Returns:
            Cached value if found and not expired, None otherwise
        """
        key = self._make_key(prefix, **kwargs)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats["misses"] += 1
                logger.debug(f"Cache MISS: {key}")
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._stats["misses"] += 1
                logger.debug(f"Cache MISS (expired): {key}")
                return None

            self._stats["hits"] += 1
            age_seconds = (datetime.now() - entry.created_at).total_seconds()
            logger.debug(f"Cache HIT: {key} (age: {age_seconds:.1f}s)")
            return entry.value

    def set(
        self,
        prefix: str,
        value: Any,
        ttl: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        Set a value in the cache.

        Args:
            prefix: Cache key prefix
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
            **kwargs: Additional key components
        """
        key = self._make_key(prefix, **kwargs)
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at,
            )
            logger.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")

    def invalidate(self, prefix: str) -> int:
        """
        Invalidate all cache entries with the given prefix.

        Args:
            prefix: Cache key prefix to invalidate

        Returns:
            Number of entries invalidated
        """
        count = 0
        with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys()
                if key == prefix or key.startswith(f"{prefix}:")
            ]
            for key in keys_to_remove:
                del self._cache[key]
                count += 1

            self._stats["invalidations"] += count

        if count > 0:
            logger.info(f"Cache INVALIDATE: {prefix} ({count} entries removed)")
        return count

    def invalidate_all(self) -> int:
        """
        Clear the entire cache.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats["invalidations"] += count

        logger.info(f"Cache INVALIDATE ALL: {count} entries cleared")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests * 100
                if total_requests > 0
                else 0
            )

            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate_pct": round(hit_rate, 2),
                "invalidations": self._stats["invalidations"],
                "current_entries": len(self._cache),
            }

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of expired entries removed
        """
        count = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
                count += 1

        if count > 0:
            logger.debug(f"Cache cleanup: removed {count} expired entries")
        return count


# Global cache instance for ratings data
# TTL: 1 hour (3600 seconds)
ratings_cache = TTLCache(default_ttl=3600)


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_args: Optional[list] = None,
):
    """
    Decorator for caching function results.

    Args:
        prefix: Cache key prefix
        ttl: Time-to-live in seconds (uses default if not specified)
        key_args: List of argument names to include in cache key

    Usage:
        @cached("kenpom_ratings", ttl=3600, key_args=["season"])
        def fetch_kenpom_ratings(season: int = 2025):
            # Expensive operation...
            return ratings

        # First call: fetches data, caches it
        ratings = fetch_kenpom_ratings(season=2025)

        # Second call within 1 hour: returns cached data
        ratings = fetch_kenpom_ratings(season=2025)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from specified arguments
            cache_kwargs = {}
            if key_args:
                # Get function argument names
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())

                # Include positional args by name
                for i, arg in enumerate(args):
                    if i < len(params) and params[i] in key_args:
                        cache_kwargs[params[i]] = arg

                # Include keyword args
                for key in key_args:
                    if key in kwargs:
                        cache_kwargs[key] = kwargs[key]

            # Try to get from cache
            cached_value = ratings_cache.get(prefix, **cache_kwargs)
            if cached_value is not None:
                return cached_value

            # Call the actual function
            result = func(*args, **kwargs)

            # Cache the result if it's not None
            if result is not None:
                ratings_cache.set(prefix, result, ttl=ttl, **cache_kwargs)

            return result

        # Expose cache control methods on the wrapped function
        wrapper.invalidate_cache = lambda: ratings_cache.invalidate(prefix)
        wrapper.cache_prefix = prefix

        return wrapper

    return decorator


def invalidate_ratings_caches():
    """
    Invalidate all ratings caches (KenPom and Haslametrics).

    Called by daily_refresh to ensure fresh data is fetched.
    """
    kenpom_count = ratings_cache.invalidate("kenpom")
    hasla_count = ratings_cache.invalidate("haslametrics")

    logger.info(
        f"Ratings caches invalidated: KenPom={kenpom_count}, Haslametrics={hasla_count}"
    )

    return {
        "kenpom_invalidated": kenpom_count,
        "haslametrics_invalidated": hasla_count,
    }
