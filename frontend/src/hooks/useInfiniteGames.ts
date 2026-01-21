'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import type { TodayGame } from '@/lib/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const PAGE_SIZE = 20;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface PaginatedGamesResponse {
  game_count: number;
  total_games: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_more: boolean;
  games: TodayGame[];
}

interface UseInfiniteGamesOptions {
  days?: number;
  initialData?: TodayGame[];
}

interface UseInfiniteGamesReturn {
  games: TodayGame[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  error: string | null;
  loadMore: () => Promise<void>;
  refresh: () => Promise<void>;
  totalGames: number;
  currentPage: number;
}

// Cache entry with TTL support
interface CacheEntry {
  data: TodayGame[];
  timestamp: number;
  totalGames: number;
  hasMore: boolean;
}

// Cache for loaded pages with TTL to avoid refetching on scroll-back
const pageCache = new Map<number, CacheEntry>();

// Check if a cache entry is still valid
function isCacheValid(entry: CacheEntry | undefined): entry is CacheEntry {
  if (!entry) return false;
  return Date.now() - entry.timestamp < CACHE_TTL;
}

// Clear all cached pages
export function clearGamesCache(): void {
  pageCache.clear();
}

// Clear expired cache entries
function clearExpiredCache(): void {
  const now = Date.now();
  for (const [page, entry] of pageCache.entries()) {
    if (now - entry.timestamp >= CACHE_TTL) {
      pageCache.delete(page);
    }
  }
}

export function useInfiniteGames(options: UseInfiniteGamesOptions = {}): UseInfiniteGamesReturn {
  const { days = 7, initialData = [] } = options;

  const [games, setGames] = useState<TodayGame[]>(initialData);
  const [isLoading, setIsLoading] = useState(initialData.length === 0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(initialData.length > 0 ? 1 : 0);
  const [totalGames, setTotalGames] = useState(initialData.length);

  // Track if initial load has happened
  const initialLoadRef = useRef(initialData.length > 0);
  // Track pending request to prevent duplicates
  const pendingRequestRef = useRef(false);

  const fetchPage = useCallback(async (page: number, bypassCache = false): Promise<PaginatedGamesResponse | null> => {
    // Check cache first (unless bypassing)
    if (!bypassCache) {
      const cachedEntry = pageCache.get(page);
      if (isCacheValid(cachedEntry)) {
        return {
          games: cachedEntry.data,
          page,
          page_size: PAGE_SIZE,
          game_count: cachedEntry.data.length,
          total_games: cachedEntry.totalGames,
          total_pages: Math.ceil(cachedEntry.totalGames / PAGE_SIZE),
          has_more: cachedEntry.hasMore,
        };
      }
    }

    try {
      const response = await fetch(
        `${API_URL}/games?days=${days}&page=${page}&page_size=${PAGE_SIZE}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch games');
      }

      const data: PaginatedGamesResponse = await response.json();

      // Cache the page with timestamp
      pageCache.set(page, {
        data: data.games,
        timestamp: Date.now(),
        totalGames: data.total_games,
        hasMore: data.has_more,
      });

      // Clean up expired entries periodically
      clearExpiredCache();

      return data;
    } catch (err) {
      console.error('Error fetching games:', err);
      return null;
    }
  }, [days]);

  // Initial load
  useEffect(() => {
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;

    const loadInitialPage = async () => {
      setIsLoading(true);
      setError(null);

      const data = await fetchPage(1);

      if (data) {
        setGames(data.games);
        setCurrentPage(1);
        setTotalGames(data.total_games);
        setHasMore(data.has_more);
      } else {
        setError('Failed to load games');
      }

      setIsLoading(false);
    };

    loadInitialPage();
  }, [fetchPage]);

  const loadMore = useCallback(async () => {
    // Prevent duplicate requests
    if (pendingRequestRef.current || isLoadingMore || !hasMore) return;

    pendingRequestRef.current = true;
    setIsLoadingMore(true);
    setError(null);

    const nextPage = currentPage + 1;
    const data = await fetchPage(nextPage);

    if (data) {
      setGames(prev => {
        // Deduplicate games by ID in case of any overlap
        const existingIds = new Set(prev.map(g => g.id));
        const newGames = data.games.filter(g => !existingIds.has(g.id));
        return [...prev, ...newGames];
      });
      setCurrentPage(nextPage);
      setTotalGames(data.total_games);
      setHasMore(data.has_more);
    } else {
      setError('Failed to load more games');
    }

    setIsLoadingMore(false);
    pendingRequestRef.current = false;
  }, [currentPage, fetchPage, hasMore, isLoadingMore]);

  // Refresh function to clear cache and reload
  const refresh = useCallback(async () => {
    clearGamesCache();
    setIsLoading(true);
    setError(null);
    setCurrentPage(0);
    setGames([]);

    const data = await fetchPage(1, true);

    if (data) {
      setGames(data.games);
      setCurrentPage(1);
      setTotalGames(data.total_games);
      setHasMore(data.has_more);
    } else {
      setError('Failed to refresh games');
    }

    setIsLoading(false);
  }, [fetchPage]);

  return {
    games,
    isLoading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh,
    totalGames,
    currentPage,
  };
}
