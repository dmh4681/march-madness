'use client';

import { useState, useCallback } from 'react';
import type { GameAnalyticsResponse } from '@/lib/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const ANALYTICS_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface CacheEntry {
  data: GameAnalyticsResponse;
  timestamp: number;
}

// Cache for analytics data by game ID
const analyticsCache = new Map<string, CacheEntry>();

function isCacheValid(entry: CacheEntry | undefined): entry is CacheEntry {
  if (!entry) return false;
  return Date.now() - entry.timestamp < ANALYTICS_CACHE_TTL;
}

export function clearAnalyticsCache(): void {
  analyticsCache.clear();
}

interface UseGameAnalyticsReturn {
  analytics: GameAnalyticsResponse | null;
  isLoading: boolean;
  error: string | null;
  loadAnalytics: () => Promise<void>;
  hasLoaded: boolean;
}

export function useGameAnalytics(gameId: string): UseGameAnalyticsReturn {
  const [analytics, setAnalytics] = useState<GameAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  const loadAnalytics = useCallback(async () => {
    // Check cache first
    const cachedEntry = analyticsCache.get(gameId);
    if (isCacheValid(cachedEntry)) {
      setAnalytics(cachedEntry.data);
      setHasLoaded(true);
      return;
    }

    // Don't re-fetch if already loading
    if (isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/games/${gameId}/analytics`);

      if (!response.ok) {
        throw new Error('Failed to fetch analytics');
      }

      const data: GameAnalyticsResponse = await response.json();

      // Cache the result
      analyticsCache.set(gameId, {
        data,
        timestamp: Date.now(),
      });

      setAnalytics(data);
      setHasLoaded(true);
    } catch (err) {
      console.error('Error fetching game analytics:', err);
      setError('Failed to load analytics');
    } finally {
      setIsLoading(false);
    }
  }, [gameId, isLoading]);

  return {
    analytics,
    isLoading,
    error,
    loadAnalytics,
    hasLoaded,
  };
}
