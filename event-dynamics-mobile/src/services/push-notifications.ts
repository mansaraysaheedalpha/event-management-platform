import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { useNotificationStore } from '@/store/notification.store';

// Android notification channels
const CHANNELS = [
  {
    id: 'event-updates',
    name: 'Event Updates',
    description: 'Session starting, event changes, schedule updates',
    importance: Notifications.AndroidImportance.HIGH,
    sound: 'default' as const,
  },
  {
    id: 'messages',
    name: 'Messages',
    description: 'Direct messages, chat mentions',
    importance: Notifications.AndroidImportance.HIGH,
    sound: 'default' as const,
  },
  {
    id: 'networking',
    name: 'Networking',
    description: 'Connection requests, recommendations',
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: 'default' as const,
  },
  {
    id: 'offers',
    name: 'Offers',
    description: 'Special offers, ticket deals',
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: undefined,
  },
  {
    id: 'general',
    name: 'General',
    description: 'General updates, achievements',
    importance: Notifications.AndroidImportance.LOW,
    sound: undefined,
  },
  {
    id: 'emergency',
    name: 'Emergency Alerts',
    description: 'Critical safety alerts',
    importance: Notifications.AndroidImportance.MAX,
    sound: 'default' as const,
  },
] as const;

export async function setupNotificationChannels(): Promise<void> {
  if (Platform.OS !== 'android') return;

  for (const channel of CHANNELS) {
    await Notifications.setNotificationChannelAsync(channel.id, {
      name: channel.name,
      description: channel.description,
      importance: channel.importance,
      sound: channel.sound ?? null,
      vibrationPattern: channel.importance >= Notifications.AndroidImportance.HIGH
        ? [0, 250, 250, 250]
        : undefined,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
    });
  }
}

export async function requestNotificationPermissions(): Promise<boolean> {
  const { status: existingStatus } = await Notifications.getPermissionsAsync();

  if (existingStatus === 'granted') return true;

  const { status } = await Notifications.requestPermissionsAsync({
    ios: {
      allowAlert: true,
      allowBadge: true,
      allowSound: true,
    },
  });

  return status === 'granted';
}

export async function registerForPushNotifications(): Promise<string | null> {
  const granted = await requestNotificationPermissions();
  if (!granted) return null;

  await setupNotificationChannels();

  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({
      projectId: undefined, // Uses projectId from app.json
    });
    const token = tokenData.data;

    useNotificationStore.getState().setPushToken(token);
    return token;
  } catch (error) {
    console.error('[PushNotifications] Failed to get push token:', error);
    return null;
  }
}

export function configureNotificationHandler(): void {
  Notifications.setNotificationHandler({
    handleNotification: async () => {
      const { preferences } = useNotificationStore.getState();

      // Respect global mute
      if (preferences.globalMute) {
        return {
          shouldShowBanner: false,
          shouldShowList: false,
          shouldPlaySound: false,
          shouldSetBadge: false,
        };
      }

      // Respect quiet hours
      if (preferences.quietHoursEnabled) {
        const now = new Date();
        const currentMinutes = now.getHours() * 60 + now.getMinutes();
        const [startH, startM] = preferences.quietHoursStart.split(':').map(Number);
        const [endH, endM] = preferences.quietHoursEnd.split(':').map(Number);
        const startMinutes = startH * 60 + startM;
        const endMinutes = endH * 60 + endM;

        const isQuietTime = startMinutes < endMinutes
          ? currentMinutes >= startMinutes && currentMinutes < endMinutes
          : currentMinutes >= startMinutes || currentMinutes < endMinutes;

        if (isQuietTime) {
          return {
            shouldShowBanner: false,
            shouldShowList: true,
            shouldPlaySound: false,
            shouldSetBadge: true,
          };
        }
      }

      return {
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      };
    },
  });
}

export async function updateBadgeCount(count: number): Promise<void> {
  try {
    await Notifications.setBadgeCountAsync(count);
  } catch {
    // Badge count not supported on all platforms
  }
}

export async function scheduleLocalNotification(
  title: string,
  body: string,
  channelId: string = 'general',
  data?: Record<string, unknown>,
): Promise<string> {
  return Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: data ?? {},
      ...(Platform.OS === 'android' ? { channelId } : {}),
    },
    trigger: null, // immediate
  });
}
