import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type {
  AppNotification,
  EmergencyAlert,
  NotificationPreferences,
  NotificationType,
} from '@/types/notifications';
import { DEFAULT_PREFERENCES } from '@/types/notifications';

const MAX_NOTIFICATIONS = 100;

let notifCounter = 0;

function generateNotificationId(): string {
  notifCounter += 1;
  return `notif-${Date.now()}-${notifCounter}`;
}

interface NotificationState {
  notifications: AppNotification[];
  unreadCount: number;
  emergencyAlert: EmergencyAlert | null;
  preferences: NotificationPreferences;
  pushToken: string | null;

  // Actions
  addNotification: (notification: Omit<AppNotification, 'id' | 'isRead' | 'timestamp'>) => void;
  markAsRead: (notificationId: string) => void;
  markAllAsRead: () => void;
  removeNotification: (notificationId: string) => void;
  clearAllNotifications: () => void;
  setEmergencyAlert: (alert: EmergencyAlert | null) => void;
  dismissEmergencyAlert: () => void;
  updatePreferences: (prefs: Partial<NotificationPreferences>) => void;
  setPushToken: (token: string | null) => void;
  getNotificationsByType: (type: NotificationType) => AppNotification[];
}

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set, get) => ({
      notifications: [],
      unreadCount: 0,
      emergencyAlert: null,
      preferences: DEFAULT_PREFERENCES,
      pushToken: null,

      addNotification: (notification) => {
        const newNotif: AppNotification = {
          ...notification,
          id: generateNotificationId(),
          isRead: false,
          timestamp: new Date().toISOString(),
        };

        set((state) => {
          const updated = [newNotif, ...state.notifications].slice(0, MAX_NOTIFICATIONS);
          return {
            notifications: updated,
            unreadCount: updated.filter((n) => !n.isRead).length,
          };
        });
      },

      markAsRead: (notificationId) => {
        set((state) => {
          const updated = state.notifications.map((n) =>
            n.id === notificationId ? { ...n, isRead: true } : n,
          );
          return {
            notifications: updated,
            unreadCount: updated.filter((n) => !n.isRead).length,
          };
        });
      },

      markAllAsRead: () => {
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, isRead: true })),
          unreadCount: 0,
        }));
      },

      removeNotification: (notificationId) => {
        set((state) => {
          const updated = state.notifications.filter((n) => n.id !== notificationId);
          return {
            notifications: updated,
            unreadCount: updated.filter((n) => !n.isRead).length,
          };
        });
      },

      clearAllNotifications: () => {
        set({ notifications: [], unreadCount: 0 });
      },

      setEmergencyAlert: (alert) => {
        set({ emergencyAlert: alert });
      },

      dismissEmergencyAlert: () => {
        set({ emergencyAlert: null });
      },

      updatePreferences: (prefs) => {
        set((state) => ({
          preferences: { ...state.preferences, ...prefs },
        }));
      },

      setPushToken: (token) => {
        set({ pushToken: token });
      },

      getNotificationsByType: (type) => {
        return get().notifications.filter((n) => n.type === type);
      },
    }),
    {
      name: 'notification-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        notifications: state.notifications.slice(0, 50), // persist last 50
        preferences: state.preferences,
        pushToken: state.pushToken,
      }),
      onRehydrateStorage: () => (state) => {
        // Recompute unreadCount from rehydrated notifications
        if (state) {
          state.unreadCount = state.notifications.filter((n) => !n.isRead).length;
        }
      },
    },
  ),
);
