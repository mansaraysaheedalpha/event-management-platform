// Hook for AI-powered attendee recommendations via REST API
// Ported from ../globalconnect/src/hooks/use-recommendations.ts

import { useState, useCallback, useRef, useEffect } from 'react';
import { useAuthStore } from '@/store/auth.store';
import { apiFetch } from '@/lib/api';
import type { Recommendation } from '@/types/networking';

const STALE_TIME_MS = 300_000; // 5 minutes
const REFRESH_DEBOUNCE_MS = 2_000;

interface UseRecommendationsOptions {
  eventId: string;
  autoFetch?: boolean;
}

export function useRecommendations(options: UseRecommendationsOptions) {
  const { eventId, autoFetch = true } = options;
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<Date | undefined>();
  const [expiresAt, setExpiresAt] = useState<Date | undefined>();

  const lastFetchTimeRef = useRef(0);
  const lastRefreshRef = useRef(0);
  const fetchedRef = useRef(false);
  const { token } = useAuthStore();

  interface RecommendationsResponse {
    recommendations: Recommendation[];
    total: number;
    hasMore: boolean;
    generatedAt?: string;
    expiresAt?: string;
  }

  const fetchRecommendations = useCallback(async (forceRefresh = false) => {
    if (!eventId || !token) return;

    const now = Date.now();
    if (!forceRefresh && now - lastFetchTimeRef.current < STALE_TIME_MS && recommendations.length > 0) {
      return; // data is still fresh
    }

    if (forceRefresh) {
      if (now - lastRefreshRef.current < REFRESH_DEBOUNCE_MS) return;
      setIsRefreshing(true);
      lastRefreshRef.current = now;
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const query = forceRefresh ? '?refresh=true' : '';
      const data = await apiFetch<RecommendationsResponse>(
        `/events/${eventId}/recommendations${query}`,
      );
      setRecommendations(data.recommendations);
      setTotal(data.total);
      setHasMore(data.hasMore);
      if (data.generatedAt) setGeneratedAt(new Date(data.generatedAt));
      if (data.expiresAt) setExpiresAt(new Date(data.expiresAt));
      lastFetchTimeRef.current = Date.now();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch recommendations');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [eventId, token, recommendations.length]);

  useEffect(() => {
    if (autoFetch && !fetchedRef.current && eventId && token) {
      fetchedRef.current = true;
      fetchRecommendations();
    }
  }, [autoFetch, eventId, token, fetchRecommendations]);

  const refresh = useCallback(() => fetchRecommendations(true), [fetchRecommendations]);

  const markViewed = useCallback(async (recommendationId: string): Promise<boolean> => {
    try {
      await apiFetch(`/events/${eventId}/recommendations/${recommendationId}/viewed`, { method: 'POST' });
      setRecommendations(prev =>
        prev.map(r => r.id === recommendationId ? { ...r, viewed: true } : r),
      );
      return true;
    } catch {
      return false;
    }
  }, [eventId]);

  const markPinged = useCallback(async (recommendationId: string): Promise<boolean> => {
    try {
      await apiFetch(`/events/${eventId}/recommendations/${recommendationId}/pinged`, { method: 'POST' });
      setRecommendations(prev =>
        prev.map(r => r.id === recommendationId ? { ...r, pinged: true } : r),
      );
      return true;
    } catch {
      return false;
    }
  }, [eventId]);

  const markConnected = useCallback(async (recommendationId: string): Promise<boolean> => {
    try {
      await apiFetch(`/events/${eventId}/recommendations/${recommendationId}/connected`, { method: 'POST' });
      setRecommendations(prev =>
        prev.map(r => r.id === recommendationId ? { ...r, connected: true } : r),
      );
      return true;
    } catch {
      return false;
    }
  }, [eventId]);

  const isStale = expiresAt ? new Date() > expiresAt : false;
  const isEmpty = recommendations.length === 0 && !isLoading;

  const clearError = useCallback(() => setError(null), []);

  return {
    recommendations,
    isLoading,
    isRefreshing,
    error,
    total,
    hasMore,
    generatedAt,
    expiresAt,
    refresh,
    markViewed,
    markPinged,
    markConnected,
    clearError,
    isEmpty,
    isStale,
  };
}
