// Ported from ../globalconnect/src/hooks/use-expo.ts
// Expo hall & booth management via Socket.IO

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';
import type {
  ExpoHall,
  ExpoBooth,
  BoothVisit,
  BoothStaffPresence,
} from '@/types/expo';

interface ExpoState {
  hall: ExpoHall | null;
  currentBooth: ExpoBooth | null;
  currentVisit: BoothVisit | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

interface SocketResponse {
  success: boolean;
  error?: string;
  hall?: ExpoHall;
  booth?: ExpoBooth;
  visitId?: string;
}

interface UseExpoOptions {
  eventId: string;
  autoConnect?: boolean;
}

export function useExpo({ eventId, autoConnect = true }: UseExpoOptions) {
  const [state, setState] = useState<ExpoState>({
    hall: null,
    currentBooth: null,
    currentVisit: null,
    isConnected: false,
    isLoading: false,
    error: null,
  });

  const { token, user } = useAuthStore();
  const socketRef = useRef<Socket | null>(null);
  const eventIdRef = useRef(eventId);
  const currentBoothIdRef = useRef<string | null>(null);

  useEffect(() => {
    eventIdRef.current = eventId;
  }, [eventId]);

  // Socket connection
  useEffect(() => {
    if (!eventId || !token || !autoConnect) return;

    const newSocket = io(`${env.REALTIME_URL}/events`, {
      auth: { token: `Bearer ${token}` },
      query: { eventId },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketRef.current = newSocket;

    newSocket.on('connect', () => {
      setState((prev) => {
        if (prev.currentBooth) {
          newSocket.emit('expo.booth.join', { boothId: prev.currentBooth.id });
        }
        return { ...prev, isConnected: true, error: null };
      });
    });

    newSocket.on('disconnect', () => {
      setState((prev) => ({ ...prev, isConnected: false }));
    });

    newSocket.on('connect_error', (error) => {
      setState((prev) => ({ ...prev, error: error.message }));
    });

    newSocket.on(
      'expo.booth.visitors.update',
      (data: { boothId: string; visitorCount: number }) => {
        setState((prev) => {
          if (!prev.hall) return prev;
          return {
            ...prev,
            hall: {
              ...prev.hall,
              booths: prev.hall.booths.map((b) =>
                b.id === data.boothId
                  ? { ...b, _count: { ...b._count, visits: data.visitorCount } }
                  : b,
              ),
            },
            currentBooth:
              prev.currentBooth?.id === data.boothId
                ? { ...prev.currentBooth, _count: { ...prev.currentBooth._count, visits: data.visitorCount } }
                : prev.currentBooth,
          };
        });
      },
    );

    newSocket.on(
      'expo.booth.staff.available',
      (data: { boothId: string; staff: BoothStaffPresence[] }) => {
        setState((prev) => {
          if (!prev.hall) return prev;
          return {
            ...prev,
            hall: {
              ...prev.hall,
              booths: prev.hall.booths.map((b) =>
                b.id === data.boothId ? { ...b, staffPresence: data.staff } : b,
              ),
            },
            currentBooth:
              prev.currentBooth?.id === data.boothId
                ? { ...prev.currentBooth, staffPresence: data.staff }
                : prev.currentBooth,
          };
        });
      },
    );

    return () => {
      newSocket.off('connect');
      newSocket.off('disconnect');
      newSocket.off('connect_error');
      newSocket.off('expo.booth.visitors.update');
      newSocket.off('expo.booth.staff.available');
      newSocket.disconnect();
      socketRef.current = null;
    };
  }, [eventId, token, autoConnect]);

  const emitWithCallback = useCallback(
    <T extends SocketResponse>(
      event: string,
      payload: Record<string, unknown>,
    ): Promise<T> => {
      return new Promise((resolve, reject) => {
        const socket = socketRef.current;
        if (!socket?.connected) {
          reject(new Error('Not connected to server'));
          return;
        }
        socket.emit(event, payload, (response: T) => {
          if (response?.success) {
            resolve(response);
          } else {
            reject(new Error(response?.error || 'Unknown error'));
          }
        });
      });
    },
    [],
  );

  const enterHall = useCallback(async (): Promise<ExpoHall | null> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const response = await emitWithCallback<SocketResponse>('expo.enter', {
        eventId: eventIdRef.current,
      });
      setState((prev) => ({
        ...prev,
        hall: response.hall || null,
        isLoading: false,
      }));
      return response.hall || null;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to enter expo hall';
      setState((prev) => ({ ...prev, isLoading: false, error: message }));
      return null;
    }
  }, [emitWithCallback]);

  const leaveHall = useCallback(async (): Promise<boolean> => {
    try {
      await emitWithCallback('expo.leave', { eventId: eventIdRef.current });
      setState((prev) => ({ ...prev, hall: null, currentBooth: null, currentVisit: null }));
      return true;
    } catch {
      return false;
    }
  }, [emitWithCallback]);

  const enterBooth = useCallback(
    async (boothId: string): Promise<ExpoBooth | null> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const response = await emitWithCallback<SocketResponse & { visitId: string }>(
          'expo.booth.enter',
          { boothId, eventId: eventIdRef.current },
        );
        currentBoothIdRef.current = boothId;
        setState((prev) => ({
          ...prev,
          currentBooth: response.booth || null,
          currentVisit: response.visitId
            ? {
                id: response.visitId,
                boothId,
                userId: user?.id || '',
                eventId: eventIdRef.current,
                enteredAt: new Date().toISOString(),
                exitedAt: null,
                status: 'BROWSING',
                durationSeconds: 0,
                leadCaptured: false,
              }
            : null,
          isLoading: false,
        }));
        return response.booth || null;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to enter booth';
        setState((prev) => ({ ...prev, isLoading: false, error: message }));
        return null;
      }
    },
    [emitWithCallback, user?.id],
  );

  const leaveBooth = useCallback(async (): Promise<boolean> => {
    const boothId = currentBoothIdRef.current;
    if (!boothId) return false;
    try {
      await emitWithCallback('expo.booth.leave', { boothId });
      currentBoothIdRef.current = null;
      setState((prev) => ({ ...prev, currentBooth: null, currentVisit: null }));
      return true;
    } catch {
      return false;
    }
  }, [emitWithCallback]);

  const trackResourceDownload = useCallback(
    async (boothId: string, resourceId: string): Promise<boolean> => {
      try {
        await emitWithCallback('expo.booth.resource.download', { boothId, resourceId });
        return true;
      } catch {
        return false;
      }
    },
    [emitWithCallback],
  );

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const getBoothsByCategory = useMemo(() => {
    return (category: string | null) => {
      if (!state.hall) return [];
      if (!category) return state.hall.booths;
      return state.hall.booths.filter((b) => b.category === category);
    };
  }, [state.hall]);

  const boothsWithOnlineStaff = useMemo(() => {
    if (!state.hall) return [];
    return state.hall.booths.filter((b) =>
      b.staffPresence.some((s) => s.status === 'ONLINE'),
    );
  }, [state.hall]);

  const categories = useMemo(() => state.hall?.categories || [], [state.hall]);

  return {
    hall: state.hall,
    booths: state.hall?.booths || [],
    currentBooth: state.currentBooth,
    currentVisit: state.currentVisit,
    isConnected: state.isConnected,
    isLoading: state.isLoading,
    error: state.error,
    categories,
    boothsWithOnlineStaff,
    getBoothsByCategory,
    enterHall,
    leaveHall,
    enterBooth,
    leaveBooth,
    trackResourceDownload,
    clearError,
  };
}
