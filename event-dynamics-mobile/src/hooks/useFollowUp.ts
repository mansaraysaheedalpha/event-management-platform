// Hook for follow-up actions via REST API
// Ported from ../globalconnect/src/hooks/use-follow-up.ts

import { useState, useCallback } from 'react';
import { useAuthStore } from '@/store/auth.store';
import { apiFetch } from '@/lib/api';
import type { Connection, FollowUpStats } from '@/types/networking';

export function useFollowUp() {
  const [pendingFollowUps, setPendingFollowUps] = useState<Connection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token } = useAuthStore();

  const fetchPendingFollowUps = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Connection[]>('/follow-up/pending');
      setPendingFollowUps(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch pending follow-ups');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  const sendFollowUp = useCallback(async (
    connectionId: string,
    message: string,
    subject?: string,
  ): Promise<boolean> => {
    setIsSending(true);
    setError(null);
    try {
      await apiFetch(`/follow-up/${connectionId}/send`, {
        method: 'POST',
        body: JSON.stringify({ message, subject }),
      });
      setPendingFollowUps(prev => prev.filter(c => c.id !== connectionId));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send follow-up');
      return false;
    } finally {
      setIsSending(false);
    }
  }, []);

  const markReplied = useCallback(async (connectionId: string): Promise<boolean> => {
    try {
      await apiFetch(`/follow-up/${connectionId}/replied`, { method: 'POST' });
      return true;
    } catch {
      return false;
    }
  }, []);

  const getFollowUpStats = useCallback(async (eventId: string): Promise<FollowUpStats | null> => {
    try {
      return await apiFetch<FollowUpStats>(`/follow-up/stats/${eventId}`);
    } catch {
      return null;
    }
  }, []);

  const scheduleEventFollowUps = useCallback(async (
    eventId: string,
    scheduledFor?: string,
  ): Promise<{ scheduledCount: number; userCount: number } | null> => {
    try {
      return await apiFetch('/follow-up/schedule', {
        method: 'POST',
        body: JSON.stringify({ eventId, scheduledFor }),
      });
    } catch {
      return null;
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    pendingFollowUps,
    isLoading,
    isSending,
    error,
    fetchPendingFollowUps,
    sendFollowUp,
    markReplied,
    getFollowUpStats,
    scheduleEventFollowUps,
    clearError,
  };
}
