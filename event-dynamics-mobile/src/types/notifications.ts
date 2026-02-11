// Notification type definitions — mirrors web app's use-notifications.ts

export type NotificationType =
  | 'session_reminder'
  | 'personal'
  | 'emergency'
  | 'schedule_change'
  | 'achievement'
  | 'dm'
  | 'mention'
  | 'agent_anomaly'
  | 'agent_intervention';

export type NotificationSeverity = 'low' | 'medium' | 'high' | 'critical';

export type ScheduleChangeType = 'time_change' | 'room_change' | 'cancelled' | 'added';

export type EmergencyAlertType = 'MEDICAL' | 'FIRE' | 'SECURITY' | 'EVACUATION';

export interface AppNotification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  actionUrl?: string;
  // Type-specific fields
  sessionId?: string;
  sessionTitle?: string;
  eventId?: string;
  startsIn?: number;
  severity?: NotificationSeverity;
  alertType?: EmergencyAlertType;
  changeType?: ScheduleChangeType;
  oldValue?: string;
  newValue?: string;
}

export interface EmergencyAlert {
  id: string;
  alertType: EmergencyAlertType;
  message: string;
  severity: NotificationSeverity;
  timestamp: string;
  eventId: string;
}

// Socket event payloads (from real-time-service)
export interface SessionReminderPayload {
  type: 'SESSION_REMINDER';
  targetUserId: string;
  sessionData: {
    id: string;
    title: string;
    startTime: string;
  };
  minutesUntilStart: number;
}

export interface PersonalNotificationPayload {
  type: 'PERSONAL_NOTIFICATION';
  targetUserId: string;
  title: string;
  message: string;
  actionUrl?: string;
}

export interface EmergencyAlertPayload {
  type: 'EMERGENCY_ALERT';
  eventId: string;
  alertType: EmergencyAlertType;
  message: string;
  severity: NotificationSeverity;
}

export interface ScheduleChangePayload {
  type: 'SCHEDULE_CHANGE';
  eventId: string;
  changeType: ScheduleChangeType;
  sessionId: string;
  sessionTitle: string;
  oldValue?: string;
  newValue?: string;
}

// Notification preferences
export type NotificationCategory = 'event_updates' | 'messages' | 'networking' | 'offers' | 'general';

export interface NotificationPreferences {
  event_updates: boolean;
  messages: boolean;
  networking: boolean;
  offers: boolean;
  general: boolean;
  quietHoursEnabled: boolean;
  quietHoursStart: string; // HH:mm
  quietHoursEnd: string;   // HH:mm
  globalMute: boolean;
}

export const DEFAULT_PREFERENCES: NotificationPreferences = {
  event_updates: true,
  messages: true,
  networking: true,
  offers: true,
  general: true,
  quietHoursEnabled: false,
  quietHoursStart: '22:00',
  quietHoursEnd: '08:00',
  globalMute: false,
};

// Toast types
export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastMessage {
  id: string;
  title: string;
  message?: string;
  type: ToastType;
  duration?: number;
  actionUrl?: string;
}

// Map notification types to categories for preference filtering
export function getNotificationCategory(type: NotificationType): NotificationCategory {
  switch (type) {
    case 'session_reminder':
    case 'schedule_change':
    case 'emergency':
      return 'event_updates';
    case 'dm':
    case 'mention':
      return 'messages';
    case 'personal':
      return 'networking';
    case 'achievement':
      return 'general';
    case 'agent_anomaly':
    case 'agent_intervention':
      return 'general';
    default:
      return 'general';
  }
}
