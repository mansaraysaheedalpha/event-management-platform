import React, { useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SectionList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, typography, spacing } from '@/theme';
import type { NotificationsStackParamList } from '@/navigation/types';
import { useNotifications } from '@/hooks/useNotifications';
import { NotificationItem } from '@/components/notifications/NotificationItem';
import { EmergencyBanner } from '@/components/notifications/EmergencyBanner';
import type { AppNotification } from '@/types/notifications';
import {
  isToday,
  isYesterday,
  isThisWeek,
  compareDesc,
} from 'date-fns';

interface NotificationSection {
  title: string;
  data: AppNotification[];
}

function groupNotifications(notifications: AppNotification[]): NotificationSection[] {
  const today: AppNotification[] = [];
  const yesterday: AppNotification[] = [];
  const thisWeek: AppNotification[] = [];
  const earlier: AppNotification[] = [];

  const sorted = [...notifications].sort((a, b) =>
    compareDesc(new Date(a.timestamp), new Date(b.timestamp)),
  );

  for (const notif of sorted) {
    const date = new Date(notif.timestamp);
    if (isToday(date)) {
      today.push(notif);
    } else if (isYesterday(date)) {
      yesterday.push(notif);
    } else if (isThisWeek(date, { weekStartsOn: 1 })) {
      thisWeek.push(notif);
    } else {
      earlier.push(notif);
    }
  }

  const sections: NotificationSection[] = [];
  if (today.length > 0) sections.push({ title: 'Today', data: today });
  if (yesterday.length > 0) sections.push({ title: 'Yesterday', data: yesterday });
  if (thisWeek.length > 0) sections.push({ title: 'This Week', data: thisWeek });
  if (earlier.length > 0) sections.push({ title: 'Earlier', data: earlier });

  return sections;
}

type NavigationProp = NativeStackNavigationProp<NotificationsStackParamList, 'NotificationsList'>;

export function NotificationsListScreen() {
  const navigation = useNavigation<NavigationProp>();
  const {
    notifications,
    unreadCount,
    emergencyAlert,
    markAsRead,
    markAllAsRead,
    dismissEmergencyAlert,
  } = useNotifications();

  const [refreshing, setRefreshing] = React.useState(false);

  const sections = useMemo(() => groupNotifications(notifications), [notifications]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    // Notifications are real-time via socket — refresh is instant
    setTimeout(() => setRefreshing(false), 500);
  }, []);

  const handleNotificationPress = useCallback(
    (notification: AppNotification) => {
      // Navigate based on notification type and data
      const tabNav = navigation.getParent();
      if (!tabNav) return;

      if (notification.sessionId && notification.eventId) {
        (tabNav as any).navigate('HomeTab', {
          screen: 'SessionDetail',
          params: {
            eventId: notification.eventId,
            sessionId: notification.sessionId,
          },
        });
      } else if (notification.eventId) {
        (tabNav as any).navigate('HomeTab', {
          screen: 'EventHub',
          params: { eventId: notification.eventId },
        });
      } else if (notification.type === 'dm' || notification.type === 'mention') {
        (tabNav as any).navigate('NetworkingTab', {
          screen: 'DirectMessages',
        });
      }
    },
    [navigation],
  );

  const renderItem = useCallback(
    ({ item }: { item: AppNotification }) => (
      <NotificationItem
        notification={item}
        onPress={handleNotificationPress}
        onMarkAsRead={markAsRead}
      />
    ),
    [handleNotificationPress, markAsRead],
  );

  const renderSectionHeader = useCallback(
    ({ section }: { section: NotificationSection }) => (
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{section.title}</Text>
      </View>
    ),
    [],
  );

  const keyExtractor = useCallback((item: AppNotification) => item.id, []);

  const ListEmptyComponent = useMemo(
    () => (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>🔔</Text>
        <Text style={styles.emptyTitle}>No notifications yet</Text>
        <Text style={styles.emptySubtitle}>
          You'll see event updates, messages, and alerts here
        </Text>
      </View>
    ),
    [],
  );

  const ItemSeparator = useCallback(
    () => <View style={styles.separator} />,
    [],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {emergencyAlert && (
        <EmergencyBanner alert={emergencyAlert} onDismiss={dismissEmergencyAlert} />
      )}

      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle} accessibilityRole="header">Notifications</Text>
          {unreadCount > 0 && (
            <Text style={styles.unreadLabel}>
              {unreadCount} unread
            </Text>
          )}
        </View>
        <View style={styles.headerActions}>
          {unreadCount > 0 && (
            <TouchableOpacity onPress={markAllAsRead} style={styles.markAllButton} accessibilityRole="button" accessibilityLabel="Mark all notifications as read">
              <Text style={styles.markAllText}>Mark all read</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            onPress={() => navigation.navigate('NotificationPreferences')}
            style={styles.settingsButton}
            accessibilityRole="button"
            accessibilityLabel="Notification settings"
          >
            <Text style={styles.settingsIcon}>⚙</Text>
          </TouchableOpacity>
        </View>
      </View>

      <SectionList
        sections={sections}
        keyExtractor={keyExtractor}
        renderItem={renderItem}
        renderSectionHeader={renderSectionHeader}
        ItemSeparatorComponent={ItemSeparator}
        ListEmptyComponent={ListEmptyComponent}
        stickySectionHeadersEnabled
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.primary.gold}
            colors={[colors.primary.gold]}
          />
        }
        contentContainerStyle={
          sections.length === 0 ? styles.emptyList : undefined
        }
        initialNumToRender={15}
        maxToRenderPerBatch={10}
        windowSize={5}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    ...typography.h2,
    color: colors.foreground,
  },
  unreadLabel: {
    ...typography.caption,
    color: colors.primary.gold,
    marginTop: 2,
  },
  markAllButton: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
  },
  markAllText: {
    ...typography.label,
    color: colors.primary.gold,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  settingsButton: {
    padding: spacing.sm,
  },
  settingsIcon: {
    fontSize: 20,
    color: colors.neutral[500],
  },
  sectionHeader: {
    backgroundColor: colors.neutral[50],
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  sectionTitle: {
    ...typography.caption,
    fontWeight: '600',
    color: colors.neutral[500],
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
    marginLeft: spacing.base + spacing.sm + 40 + spacing.md,
  },
  emptyList: {
    flex: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing['2xl'],
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.base,
  },
  emptyTitle: {
    ...typography.h3,
    color: colors.foreground,
    marginBottom: spacing.sm,
  },
  emptySubtitle: {
    ...typography.body,
    color: colors.neutral[500],
    textAlign: 'center',
  },
});
