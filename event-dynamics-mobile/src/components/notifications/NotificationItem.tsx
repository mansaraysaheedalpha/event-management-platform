import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, typography, spacing, borderRadius } from '@/theme';
import type { AppNotification, NotificationType } from '@/types/notifications';
import { formatDistanceToNow } from 'date-fns';

// Icon/color mapping per notification type
const TYPE_CONFIG: Record<NotificationType, { icon: string; color: string }> = {
  session_reminder: { icon: '🕐', color: colors.info },
  personal: { icon: '👤', color: colors.success },
  emergency: { icon: '🚨', color: colors.destructive },
  schedule_change: { icon: '📅', color: '#8B5CF6' },
  achievement: { icon: '🏆', color: colors.primary.gold },
  dm: { icon: '💬', color: colors.success },
  mention: { icon: '💬', color: colors.success },
  agent_anomaly: { icon: '📊', color: colors.warning },
  agent_intervention: { icon: '🤖', color: '#8B5CF6' },
};

interface NotificationItemProps {
  notification: AppNotification;
  onPress: (notification: AppNotification) => void;
  onMarkAsRead?: (id: string) => void;
}

export function NotificationItem({ notification, onPress, onMarkAsRead }: NotificationItemProps) {
  const config = TYPE_CONFIG[notification.type] ?? { icon: '🔔', color: colors.neutral[400] };
  const timeAgo = formatDistanceToNow(new Date(notification.timestamp), { addSuffix: true });

  const handlePress = () => {
    if (!notification.isRead && onMarkAsRead) {
      onMarkAsRead(notification.id);
    }
    onPress(notification);
  };

  return (
    <TouchableOpacity
      style={[styles.container, !notification.isRead && styles.unread]}
      onPress={handlePress}
      activeOpacity={0.7}
    >
      {!notification.isRead && <View style={[styles.unreadDot, { backgroundColor: config.color }]} />}
      <View style={[styles.iconContainer, { backgroundColor: config.color + '1A' }]}>
        <Text style={styles.iconText}>{config.icon}</Text>
      </View>
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title} numberOfLines={1}>
            {notification.title}
          </Text>
          <Text style={styles.time}>{timeAgo}</Text>
        </View>
        <Text style={styles.message} numberOfLines={2}>
          {notification.message}
        </Text>
        {notification.type === 'schedule_change' && notification.changeType && (
          <View style={[styles.changeTag, getChangeTagStyle(notification.changeType)]}>
            <Text style={styles.changeTagText}>
              {notification.changeType.replace(/_/g, ' ')}
            </Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
}

function getChangeTagStyle(changeType: string) {
  switch (changeType) {
    case 'cancelled':
      return { backgroundColor: colors.destructiveLight };
    case 'time_change':
    case 'room_change':
      return { backgroundColor: colors.warningLight };
    case 'added':
      return { backgroundColor: colors.successLight };
    default:
      return { backgroundColor: colors.neutral[100] };
  }
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    backgroundColor: colors.card,
  },
  unread: {
    backgroundColor: colors.infoLight + '33',
  },
  unreadDot: {
    position: 'absolute',
    left: spacing.sm,
    top: spacing.lg,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
    marginLeft: spacing.sm,
  },
  iconText: {
    fontSize: 18,
  },
  content: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  title: {
    ...typography.label,
    color: colors.foreground,
    flex: 1,
    marginRight: spacing.sm,
  },
  time: {
    ...typography.caption,
    color: colors.neutral[400],
  },
  message: {
    ...typography.bodySmall,
    color: colors.neutral[600],
    lineHeight: 18,
  },
  changeTag: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    marginTop: spacing.xs,
  },
  changeTagText: {
    ...typography.caption,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
});
