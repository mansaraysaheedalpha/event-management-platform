// Ported from ../globalconnect/src/hooks/use-leads.ts
// Lead management with REST API + Socket.IO real-time updates

import { useState, useEffect, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { useLeadsStore } from '@/store/leads.store';
import { env } from '@/lib/env';
import type {
  Lead,
  LeadStats,
  LeadUpdate,
  LeadCapturedEvent,
  LeadIntentUpdatedEvent,
} from '@/types/leads';

interface UseLeadsOptions {
  sponsorId: string;
  enabled?: boolean;
  limit?: number;
  intentLevel?: 'hot' | 'warm' | 'cold';
}

export function useLeads({
  sponsorId,
  enabled = true,
  limit = 50,
  intentLevel,
}: UseLeadsOptions) {
  const { token } = useAuthStore();
  const store = useLeadsStore();

  const leads = intentLevel
    ? store.leads.filter((l) => l.intent_level === intentLevel)
    : store.leads;

  const [offset, setOffset] = useState(0);
  const [hasNextPage, setHasNextPage] = useState(true);
  const [isFetchingNextPage, setIsFetchingNextPage] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [statsError, setStatsError] = useState<Error | null>(null);
  const [isRealTimeConnected, setIsRealTimeConnected] = useState(false);

  const socketRef = useRef<Socket | null>(null);
  const isMountedRef = useRef(true);

  const fetchLeads = useCallback(
    async (isNextPage = false) => {
      if (!token || !sponsorId || !enabled) return;

      if (isNextPage) {
        setIsFetchingNextPage(true);
      } else {
        store.setLoading(true);
      }
      setError(null);

      try {
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        params.set('skip', String(isNextPage ? offset : 0));
        if (intentLevel) params.set('intent_level', intentLevel);

        const response = await fetch(
          `${env.EVENT_SERVICE_URL}/sponsors/sponsors/${sponsorId}/leads?${params}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          },
        );

        if (!response.ok) throw new Error(`Failed to fetch leads: ${response.status}`);

        const data: Lead[] = await response.json();
        if (!isMountedRef.current) return;

        if (isNextPage) {
          store.setLeads([...store.leads, ...data]);
        } else {
          store.setLeads(data);
        }
        setHasNextPage(data.length === limit);
        setOffset(isNextPage ? offset + data.length : data.length);
      } catch (err) {
        if (isMountedRef.current) {
          setError(err as Error);
          store.setLoading(false);
        }
      } finally {
        if (isMountedRef.current) setIsFetchingNextPage(false);
      }
    },
    [token, sponsorId, enabled, limit, offset, intentLevel, store],
  );

  const fetchStats = useCallback(async () => {
    if (!token || !sponsorId || !enabled) return;

    store.setLoadingStats(true);
    setStatsError(null);

    try {
      const response = await fetch(
        `${env.EVENT_SERVICE_URL}/sponsors/sponsors/${sponsorId}/leads/stats`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        },
      );

      if (!response.ok) throw new Error(`Failed to fetch stats: ${response.status}`);

      const data: LeadStats = await response.json();
      if (isMountedRef.current) store.setStats(data);
    } catch (err) {
      if (isMountedRef.current) {
        setStatsError(err as Error);
        store.setLoadingStats(false);
      }
    }
  }, [token, sponsorId, enabled, store]);

  const refetch = useCallback(() => {
    setOffset(0);
    fetchLeads(false);
    fetchStats();
  }, [fetchLeads, fetchStats]);

  const fetchNextPage = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage && !store.isLoading) {
      fetchLeads(true);
    }
  }, [hasNextPage, isFetchingNextPage, store.isLoading, fetchLeads]);

  const updateLead = useCallback(
    async (leadId: string, update: LeadUpdate): Promise<Lead> => {
      if (!token || !sponsorId) throw new Error('Not authenticated');

      store.optimisticUpdateLead(leadId, update);

      try {
        const response = await fetch(
          `${env.EVENT_SERVICE_URL}/sponsors/sponsors/${sponsorId}/leads/${leadId}`,
          {
            method: 'PATCH',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(update),
          },
        );

        if (!response.ok) {
          store.rollbackUpdate(leadId);
          throw new Error(`Failed to update lead: ${response.status}`);
        }

        const updatedLead: Lead = await response.json();
        store.commitUpdate(leadId);

        if (update.follow_up_status) fetchStats();

        return updatedLead;
      } catch (err) {
        store.rollbackUpdate(leadId);
        throw err;
      }
    },
    [token, sponsorId, fetchStats, store],
  );

  // Initial fetch
  useEffect(() => {
    isMountedRef.current = true;
    if (enabled && sponsorId && token) {
      store.setSponsorId(sponsorId);
      setOffset(0);
      setHasNextPage(true);
      fetchLeads(false);
      fetchStats();
    }
    return () => {
      isMountedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, sponsorId, token, intentLevel]);

  // WebSocket for real-time updates
  useEffect(() => {
    if (!token || !sponsorId || !enabled) return;

    const socket = io(`${env.REALTIME_URL}/events`, {
      auth: { token: `Bearer ${token}` },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      if (isMountedRef.current) setIsRealTimeConnected(true);
      socket.emit(
        'sponsor.leads.join',
        { sponsorId },
        (response: { success: boolean }) => {
          if (!response.success) {
            console.warn('[useLeads] Failed to join leads room');
          }
        },
      );
    });

    socket.on('disconnect', () => {
      if (isMountedRef.current) setIsRealTimeConnected(false);
    });

    socket.on('lead.captured.new', (data: LeadCapturedEvent) => {
      if (isMountedRef.current) store.handleLeadCaptured(data);
    });

    socket.on('lead.intent.updated', (data: LeadIntentUpdatedEvent) => {
      if (isMountedRef.current) store.handleIntentUpdated(data);
    });

    socket.on('lead.stats.updated', (data: LeadStats) => {
      if (isMountedRef.current) store.handleStatsUpdated(data);
    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('lead.captured.new');
      socket.off('lead.intent.updated');
      socket.off('lead.stats.updated');
      socket.disconnect();
      socketRef.current = null;
    };
  }, [token, sponsorId, enabled, store]);

  return {
    leads,
    stats: store.stats,
    isLoading: store.isLoading,
    isLoadingStats: store.isLoadingStats,
    isFetchingNextPage,
    error,
    statsError,
    hasNextPage,
    fetchNextPage,
    refetch,
    updateLead,
    isRealTimeConnected,
  };
}
