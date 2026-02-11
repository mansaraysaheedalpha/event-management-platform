// Real-time live dashboard data via Socket.IO
// Ported from ../globalconnect/src/hooks/use-live-dashboard.ts

import { useState, useEffect } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';

interface CheckInItem {
  id?: string;
  name: string;
  timestamp?: string;
}

interface BackendDashboardData {
  totalMessages?: number;
  totalVotes?: number;
  pollVotes?: number;
  totalQuestions?: number;
  questionsAsked?: number;
  totalUpvotes?: number;
  questionUpvotes?: number;
  totalReactions?: number;
  reactions?: number;
  recentCheckIns?: CheckInItem[];
  liveCheckInFeed?: CheckInItem[];
}

export interface LiveDashboardData {
  totalMessages: number;
  totalVotes: number;
  totalQuestions: number;
  totalUpvotes: number;
  totalReactions: number;
  liveCheckInFeed: Array<{ id: string; name: string; timestamp?: string }>;
}

function transformDashboardData(data: BackendDashboardData): LiveDashboardData {
  const checkIns = data.recentCheckIns || data.liveCheckInFeed || [];

  return {
    totalMessages: data.totalMessages ?? 0,
    totalVotes: data.totalVotes ?? data.pollVotes ?? 0,
    totalQuestions: data.totalQuestions ?? data.questionsAsked ?? 0,
    totalUpvotes: data.totalUpvotes ?? data.questionUpvotes ?? 0,
    totalReactions: data.totalReactions ?? data.reactions ?? 0,
    liveCheckInFeed: checkIns.map((checkIn, index) => ({
      id: checkIn.id || `checkin-${index}-${checkIn.timestamp || Date.now()}`,
      name: checkIn.name,
      timestamp: checkIn.timestamp,
    })),
  };
}

export function useLiveDashboard(eventId: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [isJoined, setIsJoined] = useState(false);
  const [dashboardData, setDashboardData] = useState<LiveDashboardData | null>(null);
  const { token } = useAuthStore();

  useEffect(() => {
    if (!eventId || !token) return;

    const realtimeUrl = `${env.REALTIME_URL}/events`;

    const newSocket = io(realtimeUrl, {
      auth: { token: `Bearer ${token}` },
      query: { eventId },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    newSocket.on('connect', () => {
      setIsConnected(true);
    });

    // Must emit dashboard.join AFTER connectionAcknowledged, not after connect
    newSocket.on('connectionAcknowledged', () => {
      newSocket.emit(
        'dashboard.join',
        (response: { success: boolean; error?: string }) => {
          if (response?.success) {
            setIsJoined(true);
          }
        },
      );

      // Optimistic fallback if callback is not called
      setTimeout(() => {
        setIsJoined((current) => (current ? current : true));
      }, 1000);
    });

    newSocket.on('disconnect', () => {
      setIsConnected(false);
      setIsJoined(false);
    });

    newSocket.on('dashboard.update', (data: BackendDashboardData) => {
      setIsJoined(true);
      setDashboardData(transformDashboardData(data));
    });

    newSocket.on('dashboard.checkin', (data: CheckInItem) => {
      setDashboardData((prev) => {
        if (!prev) return prev;
        const newCheckIn = {
          id: data.id || `checkin-${Date.now()}`,
          name: data.name,
          timestamp: data.timestamp,
        };
        return {
          ...prev,
          liveCheckInFeed: [newCheckIn, ...prev.liveCheckInFeed].slice(0, 20),
        };
      });
    });

    return () => {
      newSocket.off('connect');
      newSocket.off('disconnect');
      newSocket.off('connectionAcknowledged');
      newSocket.off('dashboard.update');
      newSocket.off('dashboard.checkin');
      newSocket.off('connect_error');
      newSocket.disconnect();
    };
  }, [eventId, token]);

  return { isConnected, isJoined, dashboardData };
}
