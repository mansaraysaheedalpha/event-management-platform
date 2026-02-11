// NotificationProvider — initializes push notifications, socket listeners, and
// handles notification responses (taps from lock screen / notification center).

import React, { useEffect, useRef, createContext, useContext, useCallback } from 'react';
import * as Notifications from 'expo-notifications';
import { NavigationContainerRef } from '@react-navigation/native';
import type { EventSubscription } from 'expo-modules-core';
import { useAuthStore } from '@/store/auth.store';
import { useNotificationStore } from '@/store/notification.store';
import { initializeSocket, disconnectSocket, joinUserRoom } from '@/lib/socket';
import {
  registerForPushNotifications,
  configureNotificationHandler,
  updateBadgeCount,
} from '@/services/push-notifications';

interface NotificationContextValue {
  requestPermissions: () => Promise<boolean>;
}

const NotificationContext = createContext<NotificationContextValue>({
  requestPermissions: async () => false,
});

export function useNotificationContext() {
  return useContext(NotificationContext);
}

interface NotificationProviderProps {
  children: React.ReactNode;
  navigationRef?: React.RefObject<NavigationContainerRef<any> | null>;
}

export function NotificationProvider({ children, navigationRef }: NotificationProviderProps) {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const responseListenerRef = useRef<EventSubscription | null>(null);
  const receivedListenerRef = useRef<EventSubscription | null>(null);
  const initialized = useRef(false);

  // Configure notification display behavior
  useEffect(() => {
    configureNotificationHandler();
  }, []);

  // Initialize socket + push on login
  useEffect(() => {
    if (!token || !user?.id || initialized.current) return;

    initialized.current = true;

    // Socket connection
    const socket = initializeSocket(token);
    socket.on('connect', () => {
      if (user?.id) joinUserRoom(user.id);
    });

    // Push notifications
    registerForPushNotifications();

    return () => {
      disconnectSocket();
      initialized.current = false;
    };
  }, [token, user?.id]);

  // Handle notification responses (user tapped notification)
  useEffect(() => {
    responseListenerRef.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = response.notification.request.content.data;
        if (!data) return;

        // Navigate based on notification data
        const nav = navigationRef?.current;
        if (!nav?.isReady()) return;

        const type = data.type as string;
        const sessionId = data.sessionId as string | undefined;
        const eventId = data.eventId as string | undefined;

        if (sessionId && eventId) {
          nav.navigate('Main', {
            screen: 'HomeTab',
            params: {
              screen: 'SessionDetail',
              params: { eventId, sessionId },
            },
          });
        } else if (eventId) {
          nav.navigate('Main', {
            screen: 'HomeTab',
            params: {
              screen: 'EventHub',
              params: { eventId },
            },
          });
        } else if (type === 'dm' || type === 'mention') {
          nav.navigate('Main', {
            screen: 'NetworkingTab',
            params: { screen: 'DirectMessages' },
          });
        } else {
          // Default: open notifications tab
          nav.navigate('Main', {
            screen: 'NotificationsTab',
            params: { screen: 'NotificationsList' },
          });
        }
      },
    );

    // Handle notification received while app is foregrounded
    receivedListenerRef.current = Notifications.addNotificationReceivedListener(
      (_notification) => {
        // The useNotifications hook handles socket-based notifications.
        // This listener is for push notifications received while app is open.
        // We don't need to duplicate — socket already handles it.
      },
    );

    return () => {
      if (responseListenerRef.current) {
        responseListenerRef.current.remove();
      }
      if (receivedListenerRef.current) {
        receivedListenerRef.current.remove();
      }
    };
  }, [navigationRef]);

  // Sync badge count
  useEffect(() => {
    updateBadgeCount(unreadCount);
  }, [unreadCount]);

  const requestPermissions = useCallback(async () => {
    const token = await registerForPushNotifications();
    return token !== null;
  }, []);

  return (
    <NotificationContext.Provider value={{ requestPermissions }}>
      {children}
    </NotificationContext.Provider>
  );
}
