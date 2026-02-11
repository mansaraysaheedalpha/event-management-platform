// Ported from ../globalconnect/src/hooks/use-booth-chat.ts
// Real-time booth chat via Socket.IO

import { useState, useEffect, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';
import type { BoothChatMessage } from '@/types/expo';

interface BoothChatState {
  messages: BoothChatMessage[];
  hasMore: boolean;
  nextCursor: string | null;
  isConnected: boolean;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
}

interface SocketResponse {
  success: boolean;
  error?: string;
  messages?: BoothChatMessage[];
  message?: BoothChatMessage;
  hasMore?: boolean;
  nextCursor?: string | null;
}

interface UseBoothChatOptions {
  boothId: string;
  eventId: string;
  autoConnect?: boolean;
}

export function useBoothChat({
  boothId,
  eventId,
  autoConnect = true,
}: UseBoothChatOptions) {
  const [state, setState] = useState<BoothChatState>({
    messages: [],
    hasMore: false,
    nextCursor: null,
    isConnected: false,
    isLoading: false,
    isSending: false,
    error: null,
  });

  const { token, user } = useAuthStore();
  const socketRef = useRef<Socket | null>(null);
  const boothIdRef = useRef(boothId);

  useEffect(() => {
    boothIdRef.current = boothId;
  }, [boothId]);

  // Socket connection
  useEffect(() => {
    if (!boothId || !eventId || !token || !autoConnect) return;

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
      setState((prev) => ({ ...prev, isConnected: true, error: null }));
      newSocket.emit(
        'expo.booth.chat.join',
        { boothId },
        (response: SocketResponse) => {
          if (!response.success) {
            console.error('[BoothChat] Join failed:', response.error);
          }
        },
      );
    });

    newSocket.on('disconnect', () => {
      setState((prev) => ({ ...prev, isConnected: false }));
    });

    newSocket.on('connect_error', (error) => {
      setState((prev) => ({ ...prev, error: error.message }));
    });

    newSocket.on('expo.booth.chat.message', (message: BoothChatMessage) => {
      if (message.boothId !== boothIdRef.current) return;
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, message],
      }));
    });

    return () => {
      newSocket.off('connect');
      newSocket.off('disconnect');
      newSocket.off('connect_error');
      newSocket.off('expo.booth.chat.message');
      newSocket.disconnect();
      socketRef.current = null;
    };
  }, [boothId, eventId, token, autoConnect]);

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

  const loadHistory = useCallback(
    async (cursor?: string): Promise<boolean> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const response = await emitWithCallback<SocketResponse>(
          'expo.booth.chat.history',
          { boothId: boothIdRef.current, limit: 50, cursor },
        );
        setState((prev) => ({
          ...prev,
          messages: cursor
            ? [...(response.messages || []), ...prev.messages]
            : response.messages || [],
          hasMore: response.hasMore || false,
          nextCursor: response.nextCursor || null,
          isLoading: false,
        }));
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load chat history';
        setState((prev) => ({ ...prev, isLoading: false, error: message }));
        return false;
      }
    },
    [emitWithCallback],
  );

  const loadMore = useCallback(async (): Promise<boolean> => {
    if (!state.hasMore || !state.nextCursor || state.isLoading) return false;
    return loadHistory(state.nextCursor);
  }, [loadHistory, state.hasMore, state.nextCursor, state.isLoading]);

  const sendMessage = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text.trim()) return false;
      setState((prev) => ({ ...prev, isSending: true, error: null }));
      try {
        await emitWithCallback('expo.booth.chat.send', {
          boothId: boothIdRef.current,
          text: text.trim(),
        });
        setState((prev) => ({ ...prev, isSending: false }));
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to send message';
        setState((prev) => ({ ...prev, isSending: false, error: message }));
        return false;
      }
    },
    [emitWithCallback],
  );

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  // Auto-load history on connect
  useEffect(() => {
    if (state.isConnected && state.messages.length === 0) {
      loadHistory();
    }
  }, [state.isConnected, state.messages.length, loadHistory]);

  return {
    messages: state.messages,
    hasMore: state.hasMore,
    isConnected: state.isConnected,
    isLoading: state.isLoading,
    isSending: state.isSending,
    error: state.error,
    currentUserId: user?.id,
    sendMessage,
    loadMore,
    loadHistory,
    clearError,
  };
}
