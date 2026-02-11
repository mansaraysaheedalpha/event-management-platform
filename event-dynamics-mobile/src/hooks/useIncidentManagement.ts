// Real-time incident management via Socket.IO
// Ported from ../globalconnect/src/hooks/use-incident-management.ts

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { useIncidentStore } from '@/store/incident.store';
import { env } from '@/lib/env';
import type {
  Incident,
  IncidentUpdateStatus,
  UpdateIncidentPayload,
  UpdateIncidentResponse,
  JoinIncidentsResponse,
} from '@/types/incident';

interface UseIncidentManagementOptions {
  autoJoin?: boolean;
}

export function useIncidentManagement(
  options: UseIncidentManagementOptions = {},
) {
  const { autoJoin = true } = options;

  const socketRef = useRef<Socket | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const { token, user, orgId } = useAuthStore();
  const {
    incidents,
    isConnected,
    isLoading,
    error,
    filters,
    selectedIncidentId,
    setIncidents,
    addIncident,
    updateIncident,
    setIsConnected,
    setIsLoading,
    setError,
    setFilters,
    clearFilters,
    setSelectedIncidentId,
    getFilteredIncidents,
    getIncidentById,
    getActiveIncidentsCount,
    getCriticalIncidentsCount,
  } = useIncidentStore();

  // Join incidents stream
  const joinIncidentsStream = useCallback((): Promise<JoinIncidentsResponse> => {
    if (!socketRef.current?.connected) {
      const errorMsg = 'Not connected to incident management service';
      setError(errorMsg);
      return Promise.resolve({ success: false, error: errorMsg });
    }

    return new Promise((resolve) => {
      socketRef.current!.emit(
        'incidents.join',
        {},
        (response: JoinIncidentsResponse) => {
          setIsLoading(false);

          if (response.success) {
            setError(null);
            if (response.incidents && response.incidents.length > 0) {
              setIncidents(response.incidents);
            }
          } else {
            setError(response.error || 'Failed to join incidents stream');
          }

          resolve(response);
        },
      );
    });
  }, [setError, setIsLoading, setIncidents]);

  // Initialize socket connection
  useEffect(() => {
    if (!token || !user || !orgId) return;

    const realtimeUrl = `${env.REALTIME_URL}/events`;

    setIsLoading(true);

    const newSocket = io(realtimeUrl, {
      auth: { token: `Bearer ${token}` },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketRef.current = newSocket;

    newSocket.on('connect', () => {
      setIsConnected(true);
      setError(null);
      if (autoJoin) {
        joinIncidentsStream();
      }
    });

    newSocket.on('disconnect', () => {
      setIsConnected(false);
    });

    newSocket.on('connect_error', () => {
      setError('Failed to connect to incident management service');
      setIsConnected(false);
      setIsLoading(false);
    });

    newSocket.on('exception', (err: { message?: string }) => {
      setError(err?.message || 'An error occurred');
      setIsLoading(false);
    });

    newSocket.on('incident.new', (incident: Incident) => {
      addIncident(incident);
    });

    newSocket.on('incident.updated', (incident: Incident) => {
      updateIncident(incident);
    });

    return () => {
      newSocket.off('connect');
      newSocket.off('disconnect');
      newSocket.off('connect_error');
      newSocket.off('exception');
      newSocket.off('incident.new');
      newSocket.off('incident.updated');
      newSocket.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    };
  }, [
    token,
    user,
    orgId,
    autoJoin,
    addIncident,
    updateIncident,
    setIsConnected,
    setIsLoading,
    setError,
    joinIncidentsStream,
  ]);

  // Update incident status
  const updateIncidentStatus = useCallback(
    async (
      incidentId: string,
      status: IncidentUpdateStatus,
      resolutionNotes?: string,
    ): Promise<UpdateIncidentResponse> => {
      if (!socketRef.current?.connected) {
        const errorMsg = 'Not connected to incident management service';
        setUpdateError(errorMsg);
        return { success: false, error: errorMsg };
      }

      setIsUpdating(true);
      setUpdateError(null);

      const payload: UpdateIncidentPayload = {
        incidentId,
        status,
        resolutionNotes,
        idempotencyKey: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      };

      return new Promise((resolve) => {
        let hasResolved = false;

        const timeoutId = setTimeout(() => {
          if (hasResolved) return;
          hasResolved = true;
          setIsUpdating(false);
          setUpdateError('Request timed out. Please try again.');
          resolve({ success: false, error: 'Request timed out' });
        }, 10000);

        socketRef.current!.emit(
          'incident.update_status',
          payload,
          (response: UpdateIncidentResponse) => {
            if (hasResolved) return;
            hasResolved = true;
            clearTimeout(timeoutId);
            setIsUpdating(false);

            if (!response.success) {
              setUpdateError(response.error || 'Failed to update incident');
            }

            resolve(response);
          },
        );
      });
    },
    [],
  );

  const acknowledgeIncident = useCallback(
    (incidentId: string) => updateIncidentStatus(incidentId, 'ACKNOWLEDGED'),
    [updateIncidentStatus],
  );

  const startInvestigation = useCallback(
    (incidentId: string) => updateIncidentStatus(incidentId, 'INVESTIGATING'),
    [updateIncidentStatus],
  );

  const resolveIncident = useCallback(
    (incidentId: string, resolutionNotes?: string) =>
      updateIncidentStatus(incidentId, 'RESOLVED', resolutionNotes),
    [updateIncidentStatus],
  );

  const filteredIncidents = useMemo(
    () => getFilteredIncidents(),
    [incidents, filters, getFilteredIncidents],
  );

  const activeIncidentsCount = useMemo(
    () => getActiveIncidentsCount(),
    [incidents, getActiveIncidentsCount],
  );

  const criticalIncidentsCount = useMemo(
    () => getCriticalIncidentsCount(),
    [incidents, getCriticalIncidentsCount],
  );

  return {
    incidents,
    isConnected,
    isLoading,
    error,
    filters,
    selectedIncidentId,
    isUpdating,
    updateError,

    filteredIncidents,
    activeIncidentsCount,
    criticalIncidentsCount,

    acknowledgeIncident,
    startInvestigation,
    resolveIncident,
    updateIncidentStatus,

    setFilters,
    clearFilters,
    setSelectedIncidentId,
    getIncidentById,
  };
}
