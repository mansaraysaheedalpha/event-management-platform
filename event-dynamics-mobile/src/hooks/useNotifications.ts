// Main notification hook — listens to socket events and populates the notification store.
// Mirrors ../globalconnect/src/hooks/use-notifications.ts adapted for React Native.
//
// IMPORTANT: Socket event handlers read store via getState() to avoid stale closures.
// This keeps the effect deps minimal (only user.id) so socket listeners are stable.

import { useEffect, useRef } from 'react';
import { useNotificationStore } from '@/store/notification.store';
import { getSocket, joinUserRoom, leaveUserRoom } from '@/lib/socket';
import { useAuthStore } from '@/store/auth.store';
import { scheduleLocalNotification, updateBadgeCount } from '@/services/push-notifications';
import { getNotificationCategory } from '@/types/notifications';
import type {
  SessionReminderPayload,
  PersonalNotificationPayload,
  EmergencyAlertPayload,
  ScheduleChangePayload,
  NotificationType,
} from '@/types/notifications';

// Module-level helper: reads preferences at call time via getState()
function shouldShowNotification(type: NotificationType): boolean {
  const { preferences } = useNotificationStore.getState();
  if (preferences.globalMute) return false;
  const category = getNotificationCategory(type);
  return preferences[category];
}

export function useNotifications() {
  const user = useAuthStore((s) => s.user);
  // Select individual slices for stable references (Zustand actions are referentially stable)
  const notifications = useNotificationStore((s) => s.notifications);
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const emergencyAlert = useNotificationStore((s) => s.emergencyAlert);
  const markAsRead = useNotificationStore((s) => s.markAsRead);
  const markAllAsRead = useNotificationStore((s) => s.markAllAsRead);
  const removeNotification = useNotificationStore((s) => s.removeNotification);
  const clearAllNotifications = useNotificationStore((s) => s.clearAllNotifications);
  const dismissEmergencyAlert = useNotificationStore((s) => s.dismissEmergencyAlert);
  const getNotificationsByType = useNotificationStore((s) => s.getNotificationsByType);

  const listenersBound = useRef(false);

  // Bind socket listeners — only depends on user.id.
  // All handlers read store via getState() so they always see latest state
  // without causing the effect to re-run on every store update.
  useEffect(() => {
    const socket = getSocket();
    if (!socket || !user?.id || listenersBound.current) return;

    joinUserRoom(user.id);
    listenersBound.current = true;

    const handleSessionReminder = (payload: SessionReminderPayload) => {
      if (!shouldShowNotification('session_reminder')) return;

      useNotificationStore.getState().addNotification({
        type: 'session_reminder',
        title: 'Session Starting Soon',
        message: `${payload.sessionData.title} starts in ${payload.minutesUntilStart} minutes`,
        sessionId: payload.sessionData.id,
        sessionTitle: payload.sessionData.title,
        startsIn: payload.minutesUntilStart,
      });

      scheduleLocalNotification(
        'Session Starting Soon',
        `${payload.sessionData.title} starts in ${payload.minutesUntilStart} minutes`,
        'event-updates',
        { type: 'session_reminder', sessionId: payload.sessionData.id },
      );
    };

    const handlePersonalNotification = (payload: PersonalNotificationPayload) => {
      if (!shouldShowNotification('personal')) return;

      useNotificationStore.getState().addNotification({
        type: 'personal',
        title: payload.title,
        message: payload.message,
        actionUrl: payload.actionUrl,
      });

      scheduleLocalNotification(
        payload.title,
        payload.message,
        'networking',
        { type: 'personal', actionUrl: payload.actionUrl },
      );
    };

    const handleEmergencyAlert = (payload: EmergencyAlertPayload) => {
      // Emergency alerts always shown regardless of preferences
      const store = useNotificationStore.getState();

      store.setEmergencyAlert({
        id: `emergency-${Date.now()}`,
        alertType: payload.alertType,
        message: payload.message,
        severity: payload.severity,
        timestamp: new Date().toISOString(),
        eventId: payload.eventId,
      });

      store.addNotification({
        type: 'emergency',
        title: `${payload.alertType} Alert`,
        message: payload.message,
        severity: payload.severity,
        alertType: payload.alertType,
        eventId: payload.eventId,
      });

      scheduleLocalNotification(
        `${payload.severity === 'critical' ? '🚨 ' : '⚠️ '}${payload.alertType} Alert`,
        payload.message,
        'emergency',
        { type: 'emergency', eventId: payload.eventId, severity: payload.severity },
      );
    };

    const handleScheduleChange = (payload: ScheduleChangePayload) => {
      if (!shouldShowNotification('schedule_change')) return;

      const changeMessages: Record<string, string> = {
        time_change: `${payload.sessionTitle} time changed${payload.newValue ? ` to ${payload.newValue}` : ''}`,
        room_change: `${payload.sessionTitle} moved${payload.newValue ? ` to ${payload.newValue}` : ''}`,
        cancelled: `${payload.sessionTitle} has been cancelled`,
        added: `New session: ${payload.sessionTitle}`,
      };

      const message = changeMessages[payload.changeType] || `${payload.sessionTitle} updated`;

      useNotificationStore.getState().addNotification({
        type: 'schedule_change',
        title: 'Schedule Change',
        message,
        sessionId: payload.sessionId,
        sessionTitle: payload.sessionTitle,
        changeType: payload.changeType,
        oldValue: payload.oldValue,
        newValue: payload.newValue,
        eventId: payload.eventId,
      });

      scheduleLocalNotification(
        'Schedule Change',
        message,
        'event-updates',
        { type: 'schedule_change', sessionId: payload.sessionId, eventId: payload.eventId },
      );
    };

    socket.on('notification.session_reminder', handleSessionReminder);
    socket.on('notification.personal', handlePersonalNotification);
    socket.on('notification.emergency', handleEmergencyAlert);
    socket.on('notification.schedule_change', handleScheduleChange);

    return () => {
      socket.off('notification.session_reminder', handleSessionReminder);
      socket.off('notification.personal', handlePersonalNotification);
      socket.off('notification.emergency', handleEmergencyAlert);
      socket.off('notification.schedule_change', handleScheduleChange);
      if (user?.id) leaveUserRoom(user.id);
      listenersBound.current = false;
    };
  }, [user?.id]);

  // Sync badge count with unread
  useEffect(() => {
    updateBadgeCount(unreadCount);
  }, [unreadCount]);

  return {
    notifications,
    unreadCount,
    emergencyAlert,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAllNotifications,
    dismissEmergencyAlert,
    getNotificationsByType,
  };
}
