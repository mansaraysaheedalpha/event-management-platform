// Hook for managing connections via REST API
// Ported from ../globalconnect/src/hooks/use-connections.ts

import { useState, useCallback, useRef, useEffect } from 'react';
import { useAuthStore } from '@/store/auth.store';
import { apiFetch } from '@/lib/api';
import type {
  Connection,
  ConnectionStrength,
  StrengthDistribution,
  FollowUpSuggestion,
  FollowUpTone,
  ReportOutcomeDto,
  EventNetworkingStats,
  UserNetworkingStats,
} from '@/types/networking';

interface UseConnectionsOptions {
  eventId?: string;
  autoFetch?: boolean;
}

export function useConnections(options: UseConnectionsOptions = {}) {
  const { eventId, autoFetch = true } = options;
  const [connections, setConnections] = useState<Connection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user, token } = useAuthStore();
  const fetchedRef = useRef(false);

  const fetchConnections = useCallback(async () => {
    if (!user?.id || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const path = eventId
        ? `/connections/user/${user.id}/event/${eventId}`
        : `/connections/user/${user.id}`;
      const data = await apiFetch<Connection[]>(path);
      setConnections(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch connections');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id, token, eventId]);

  // Auto-fetch on mount
  useEffect(() => {
    if (autoFetch && !fetchedRef.current && user?.id && token) {
      fetchedRef.current = true;
      fetchConnections();
    }
  }, [autoFetch, user?.id, token, fetchConnections]);

  const fetchConnection = useCallback(async (connectionId: string): Promise<Connection | null> => {
    try {
      return await apiFetch<Connection>(`/connections/${connectionId}`);
    } catch {
      return null;
    }
  }, []);

  const markFollowUpSent = useCallback(async (connectionId: string): Promise<boolean> => {
    try {
      await apiFetch(`/connections/${connectionId}/follow-up/sent`, { method: 'PATCH' });
      setConnections(prev =>
        prev.map(c => c.id === connectionId ? { ...c, followUpSent: true, followUpSentAt: new Date().toISOString() } : c),
      );
      return true;
    } catch {
      return false;
    }
  }, []);

  const reportOutcome = useCallback(async (connectionId: string, outcome: ReportOutcomeDto): Promise<boolean> => {
    try {
      await apiFetch(`/connections/${connectionId}/outcome`, {
        method: 'PATCH',
        body: JSON.stringify(outcome),
      });
      setConnections(prev =>
        prev.map(c => c.id === connectionId
          ? { ...c, outcomeReported: true, outcomeType: outcome.outcomeType, outcomeNotes: outcome.notes ?? null }
          : c),
      );
      return true;
    } catch {
      return false;
    }
  }, []);

  const getEventStats = useCallback(async (eid: string): Promise<EventNetworkingStats | null> => {
    try {
      return await apiFetch<EventNetworkingStats>(`/connections/stats/event/${eid}`);
    } catch {
      return null;
    }
  }, []);

  const getUserStats = useCallback(async (): Promise<UserNetworkingStats | null> => {
    if (!user?.id) return null;
    try {
      return await apiFetch<UserNetworkingStats>(`/connections/stats/user/${user.id}`);
    } catch {
      return null;
    }
  }, [user?.id]);

  const connectionExists = useCallback(async (userAId: string, userBId: string, eid: string): Promise<boolean> => {
    try {
      const result = await apiFetch<{ exists: boolean }>(`/connections/check/${userAId}/${userBId}/${eid}`);
      return result.exists;
    } catch {
      return false;
    }
  }, []);

  const fetchConnectionsByStrength = useCallback(async (strength?: ConnectionStrength): Promise<Connection[]> => {
    if (!user?.id) return [];
    try {
      const query = strength ? `?strength=${strength}` : '';
      return await apiFetch<Connection[]>(`/connections/user/${user.id}/by-strength${query}`);
    } catch {
      return [];
    }
  }, [user?.id]);

  const getPendingFollowUps = useCallback(async (): Promise<Connection[]> => {
    if (!user?.id) return [];
    try {
      const query = eventId ? `?eventId=${eventId}` : '';
      return await apiFetch<Connection[]>(`/connections/user/${user.id}/pending-followup${query}`);
    } catch {
      return [];
    }
  }, [user?.id, eventId]);

  const generateFollowUpSuggestion = useCallback(async (
    connectionId: string,
    tone: FollowUpTone = 'professional',
    additionalContext?: string,
  ): Promise<FollowUpSuggestion | null> => {
    try {
      return await apiFetch<FollowUpSuggestion>('/follow-up/generate', {
        method: 'POST',
        body: JSON.stringify({ connectionId, tone, additionalContext }),
      });
    } catch {
      return null;
    }
  }, []);

  const sendFollowUp = useCallback(async (connectionId: string, message: string): Promise<boolean> => {
    try {
      await apiFetch(`/follow-up/${connectionId}/send`, {
        method: 'POST',
        body: JSON.stringify({ message }),
      });
      setConnections(prev =>
        prev.map(c => c.id === connectionId ? { ...c, followUpSent: true, followUpSentAt: new Date().toISOString() } : c),
      );
      return true;
    } catch {
      return false;
    }
  }, []);

  // Compute strength distribution
  const strengthDistribution: StrengthDistribution = {
    WEAK: connections.filter(c => c.strength === 'WEAK').length,
    MODERATE: connections.filter(c => c.strength === 'MODERATE').length,
    STRONG: connections.filter(c => c.strength === 'STRONG').length,
  };

  const clearError = useCallback(() => setError(null), []);

  return {
    connections,
    isLoading,
    error,
    currentUserId: user?.id,
    strengthDistribution,
    fetchConnections,
    fetchConnection,
    markFollowUpSent,
    reportOutcome,
    getEventStats,
    getUserStats,
    connectionExists,
    fetchConnectionsByStrength,
    getPendingFollowUps,
    generateFollowUpSuggestion,
    sendFollowUp,
    clearError,
  };
}
