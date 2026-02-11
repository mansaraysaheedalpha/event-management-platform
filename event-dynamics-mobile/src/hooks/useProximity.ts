// Hook for proximity-based networking via Socket.IO + expo-location
// Ported from ../globalconnect/src/hooks/use-proximity.ts
// Mobile-specific: uses expo-location instead of navigator.geolocation

import { useState, useCallback, useRef, useEffect } from 'react';
import { Alert } from 'react-native';
import { io, Socket } from 'socket.io-client';
import * as Location from 'expo-location';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';
import { isAdvancedRosterUpdate } from '@/types/networking';
import type {
  NearbyUser,
  ProximityPing,
  LocationCoordinates,
  ProximityResponse,
  RosterUpdate,
} from '@/types/networking';

const MIN_DISTANCE_METERS = 5;
const FORCED_UPDATE_INTERVAL_MS = 10_000;
const MAX_PINGS_HISTORY = 10;

function generateId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** Haversine distance between two coordinates in meters */
function haversineDistance(a: LocationCoordinates, b: LocationCoordinates): number {
  const R = 6371e3;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h = sinLat * sinLat + Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * sinLon * sinLon;
  return R * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

interface UseProximityOptions {
  eventId: string;
  autoStart?: boolean;
}

export function useProximity(options: UseProximityOptions) {
  const { eventId, autoStart = false } = options;
  const [nearbyUsers, setNearbyUsers] = useState<NearbyUser[]>([]);
  const [receivedPings, setReceivedPings] = useState<ProximityPing[]>([]);
  const [isTracking, setIsTracking] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [locationPermission, setLocationPermission] = useState<'granted' | 'denied' | 'prompt' | 'unavailable'>('prompt');
  const [lastLocation, setLastLocation] = useState<LocationCoordinates | null>(null);

  const socketRef = useRef<Socket | null>(null);
  const locationSubRef = useRef<Location.LocationSubscription | null>(null);
  const forcedUpdateRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastSentLocationRef = useRef<LocationCoordinates | null>(null);

  const { token, user } = useAuthStore();

  // Check location permission on mount
  useEffect(() => {
    (async () => {
      const { status } = await Location.getForegroundPermissionsAsync();
      if (status === 'granted') {
        setLocationPermission('granted');
      } else if (status === 'denied') {
        setLocationPermission('denied');
      } else {
        setLocationPermission('prompt');
      }
    })();
  }, []);

  const connectSocket = useCallback(() => {
    if (socketRef.current?.connected || !token) return;

    const realtimeUrl = `${env.REALTIME_URL}/events`;
    const newSocket = io(realtimeUrl, {
      auth: { token: `Bearer ${token}` },
      query: { eventId },
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
      setError(null);
    });

    newSocket.on('connectionAcknowledged', () => {
      // Socket ready
    });

    newSocket.on('disconnect', () => {
      setIsConnected(false);
    });

    newSocket.on('connect_error', (err: Error) => {
      setError(err.message);
      setIsConnected(false);
    });

    // Nearby users roster update
    newSocket.on('proximity.roster.updated', (update: RosterUpdate) => {
      if (isAdvancedRosterUpdate(update)) {
        setNearbyUsers(update.nearbyUsers.map(nu => ({
          id: nu.user.id,
          name: nu.user.name,
          avatarUrl: nu.user.avatarUrl,
          distance: nu.distance,
          sharedInterests: nu.sharedInterests,
          connectionContexts: nu.connectionContexts,
          matchScore: nu.matchScore,
          alreadyConnected: nu.alreadyConnected,
        })));
      } else {
        // Simple roster - just user IDs
        setNearbyUsers(prev => {
          const ids = new Set(update.nearbyUserIds);
          return prev.filter(u => ids.has(u.id));
        });
      }
    });

    // Incoming ping
    newSocket.on('proximity.ping.received', (data: { fromUser: { id: string; name: string }; message: string }) => {
      const ping: ProximityPing = {
        fromUser: data.fromUser,
        message: data.message || 'Hey! Want to connect?',
        receivedAt: new Date().toISOString(),
      };
      setReceivedPings(prev => [ping, ...prev].slice(0, MAX_PINGS_HISTORY));
      // Haptic feedback for incoming ping
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    });

    newSocket.on('systemError', (data: { message: string }) => {
      setError(data.message);
    });
  }, [token, eventId]);

  const sendLocationUpdate = useCallback((coords: LocationCoordinates) => {
    const socket = socketRef.current;
    if (!socket?.connected) return;

    // Skip if moved less than minimum distance
    if (lastSentLocationRef.current) {
      const distance = haversineDistance(lastSentLocationRef.current, coords);
      if (distance < MIN_DISTANCE_METERS) return;
    }

    lastSentLocationRef.current = coords;
    setLastLocation(coords);

    socket.emit('proximity.location.update', {
      latitude: coords.latitude,
      longitude: coords.longitude,
      idempotencyKey: generateId(),
      eventId,
    }, (response: ProximityResponse) => {
      if (!response.success && response.error) {
        setError(response.error);
      }
    });
  }, [eventId]);

  const startTracking = useCallback(async (): Promise<boolean> => {
    // Request permission
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') {
      setLocationPermission('denied');
      Alert.alert(
        'Location Permission Required',
        'Enable location permissions in Settings to discover nearby attendees.',
      );
      return false;
    }
    setLocationPermission('granted');

    // Connect socket
    connectSocket();

    // Start location updates (battery efficient)
    try {
      const sub = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Balanced,
          timeInterval: 5000,
          distanceInterval: 5,
        },
        (location: Location.LocationObject) => {
          sendLocationUpdate({
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
          });
        },
      );

      locationSubRef.current = sub;

      // Forced update interval
      forcedUpdateRef.current = setInterval(async () => {
        try {
          const location = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.Balanced,
          });
          sendLocationUpdate({
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
          });
        } catch {
          // Silently ignore forced update failures
        }
      }, FORCED_UPDATE_INTERVAL_MS);

      setIsTracking(true);
      return true;
    } catch (err) {
      setError('Failed to start location tracking');
      return false;
    }
  }, [connectSocket, sendLocationUpdate]);

  const stopTracking = useCallback(() => {
    // Remove location subscription
    if (locationSubRef.current) {
      locationSubRef.current.remove();
      locationSubRef.current = null;
    }

    // Clear forced update interval
    if (forcedUpdateRef.current) {
      clearInterval(forcedUpdateRef.current);
      forcedUpdateRef.current = null;
    }

    // Disconnect socket
    if (socketRef.current) {
      socketRef.current.removeAllListeners();
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    setIsTracking(false);
    setIsConnected(false);
    setNearbyUsers([]);
    lastSentLocationRef.current = null;
  }, []);

  const sendPing = useCallback(async (targetUserId: string, message?: string): Promise<boolean> => {
    const socket = socketRef.current;
    if (!socket?.connected) return false;

    return new Promise((resolve) => {
      socket.emit('proximity.ping', {
        targetUserId,
        message,
        eventId,
        idempotencyKey: generateId(),
      }, (response: ProximityResponse) => {
        if (response.success) {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        }
        resolve(response.success);
      });
    });
  }, [eventId]);

  const dismissPing = useCallback((index: number) => {
    setReceivedPings(prev => prev.filter((_, i) => i !== index));
  }, []);

  const clearPings = useCallback(() => setReceivedPings([]), []);
  const clearError = useCallback(() => setError(null), []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTracking();
    };
  }, [stopTracking]);

  // Auto-start if configured
  useEffect(() => {
    if (autoStart && locationPermission === 'granted' && !isTracking) {
      startTracking();
    }
  }, [autoStart, locationPermission, isTracking, startTracking]);

  return {
    nearbyUsers,
    receivedPings,
    isTracking,
    isConnected,
    error,
    locationPermission,
    lastLocation,
    currentUserId: user?.id,
    startTracking,
    stopTracking,
    sendPing,
    dismissPing,
    clearPings,
    clearError,
  };
}
