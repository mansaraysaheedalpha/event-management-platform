// Ported from ../globalconnect/src/context/SessionSocketContext.tsx
// Shared Socket.IO context for all session features (Chat, Q&A, Polls, Reactions)

import React, { createContext, useContext, useEffect, useMemo, useState, useRef, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';

interface SessionSocketContextValue {
  socket: Socket | null;
  isConnected: boolean;
  isJoined: boolean;
  connectionState: ConnectionState;
  error: string | null;
  sessionId: string;
  eventId: string;
  chatOpen: boolean;
  qaOpen: boolean;
  pollsOpen: boolean;
  reactionsOpen: boolean;
}

const SessionSocketContext = createContext<SessionSocketContextValue | null>(null);

interface SessionSocketProviderProps {
  children: ReactNode;
  sessionId: string;
  eventId: string;
  initialChatOpen?: boolean;
  initialQaOpen?: boolean;
  initialPollsOpen?: boolean;
  initialReactionsOpen?: boolean;
}

export const SessionSocketProvider: React.FC<SessionSocketProviderProps> = ({
  children,
  sessionId,
  eventId,
  initialChatOpen = false,
  initialQaOpen = false,
  initialPollsOpen = false,
  initialReactionsOpen = false,
}) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isJoined, setIsJoined] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting');
  const [error, setError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(initialChatOpen);
  const [qaOpen, setQaOpen] = useState(initialQaOpen);
  const [pollsOpen, setPollsOpen] = useState(initialPollsOpen);
  const [reactionsOpen, setReactionsOpen] = useState(initialReactionsOpen);

  const socketRef = useRef<Socket | null>(null);
  const { token } = useAuthStore();

  useEffect(() => {
    if (!sessionId || !eventId || !token) return;

    if (socketRef.current?.connected) return;

    const realtimeUrl = `${env.REALTIME_URL}/events`;

    setConnectionState('connecting');
    setError(null);

    const newSocket = io(realtimeUrl, {
      auth: { token: `Bearer ${token}` },
      query: { sessionId, eventId },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      timeout: 20000,
    });

    socketRef.current = newSocket;

    newSocket.on('connect', () => {
      setIsConnected(true);
      setConnectionState('connected');
      setError(null);
    });

    newSocket.on('connectionAcknowledged', () => {
      newSocket.emit('session.join', { sessionId, eventId }, (response: {
        success: boolean;
        error?: { message: string; statusCode: number };
        session?: { chatOpen?: boolean; qaOpen?: boolean; pollsOpen?: boolean };
      }) => {
        if (response?.success === false) {
          const errorMsg = response.error?.message || 'Failed to join session';
          setError(errorMsg);
          setIsJoined(false);
          return;
        }

        setIsJoined(true);
        setError(null);

        if (response.session) {
          if (response.session.chatOpen !== undefined) setChatOpen(response.session.chatOpen);
          if (response.session.qaOpen !== undefined) setQaOpen(response.session.qaOpen);
          if (response.session.pollsOpen !== undefined) setPollsOpen(response.session.pollsOpen);
        }
      });
    });

    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      setIsJoined(false);
      if (reason === 'io server disconnect' || reason === 'io client disconnect') {
        setConnectionState('disconnected');
      } else {
        setConnectionState('reconnecting');
      }
    });

    newSocket.on('connect_error', (err) => {
      setError(err.message);
      setIsConnected(false);
      setConnectionState('error');
    });

    // Manager-level reconnect events (reconnect_attempt, reconnect) live on
    // newSocket.io, not the socket itself. The disconnect handler already sets
    // 'reconnecting' for transport-level disconnects, and the connect handler
    // sets 'connected' on successful reconnect, so these states are covered.

    newSocket.on('chat.status.changed', (data: { sessionId: string; isOpen: boolean }) => {
      if (data.sessionId === sessionId) setChatOpen(data.isOpen);
    });
    newSocket.on('qa.status.changed', (data: { sessionId: string; isOpen: boolean }) => {
      if (data.sessionId === sessionId) setQaOpen(data.isOpen);
    });
    newSocket.on('polls.status.changed', (data: { sessionId: string; isOpen: boolean }) => {
      if (data.sessionId === sessionId) setPollsOpen(data.isOpen);
    });
    newSocket.on('reactions.status.changed', (data: { sessionId: string; isOpen: boolean }) => {
      if (data.sessionId === sessionId) setReactionsOpen(data.isOpen);
    });

    setSocket(newSocket);

    return () => {
      socketRef.current = null;
      newSocket.emit('session.leave', { sessionId });
      newSocket.removeAllListeners();
      newSocket.disconnect();
    };
  }, [sessionId, eventId, token]);

  const value = useMemo<SessionSocketContextValue>(() => ({
    socket,
    isConnected,
    isJoined,
    connectionState,
    error,
    sessionId,
    eventId,
    chatOpen,
    qaOpen,
    pollsOpen,
    reactionsOpen,
  }), [socket, isConnected, isJoined, connectionState, error, sessionId, eventId, chatOpen, qaOpen, pollsOpen, reactionsOpen]);

  return (
    <SessionSocketContext.Provider value={value}>
      {children}
    </SessionSocketContext.Provider>
  );
};

export const useSessionSocket = (): SessionSocketContextValue => {
  const context = useContext(SessionSocketContext);
  if (!context) {
    throw new Error('useSessionSocket must be used within a SessionSocketProvider');
  }
  return context;
};
