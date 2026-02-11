// Conversation list item for DM conversations
import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Avatar } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import type { Conversation } from '@/types/networking';

interface ConversationItemProps {
  conversation: Conversation;
  isActive?: boolean;
  onPress?: (conversation: Conversation) => void;
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return 'Now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return `${Math.floor(days / 7)}w`;
}

export function ConversationItem({ conversation, isActive, onPress }: ConversationItemProps) {
  const { recipient, lastMessage, unreadCount, updatedAt } = conversation;
  const fullName = `${recipient.firstName} ${recipient.lastName}`;
  const hasUnread = unreadCount > 0;

  const handlePress = useCallback(() => onPress?.(conversation), [conversation, onPress]);

  return (
    <Pressable
      onPress={handlePress}
      style={[styles.container, isActive && styles.active]}
    >
      <View style={styles.avatarWrap}>
        <Avatar uri={recipient.avatar ?? undefined} name={fullName} size={48} />
        {recipient.isOnline && <View style={styles.onlineDot} />}
      </View>

      <View style={styles.content}>
        <View style={styles.topRow}>
          <Text style={[styles.name, hasUnread && styles.nameBold]} numberOfLines={1}>
            {fullName}
          </Text>
          <Text style={[styles.time, hasUnread && styles.timeBold]}>
            {timeAgo(updatedAt)}
          </Text>
        </View>
        {lastMessage && (
          <Text
            style={[styles.preview, hasUnread && styles.previewBold]}
            numberOfLines={1}
          >
            {lastMessage.text}
          </Text>
        )}
      </View>

      {hasUnread && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    gap: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  active: {
    backgroundColor: colors.neutral[50],
  },
  avatarWrap: {
    position: 'relative',
  },
  onlineDot: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.success,
    borderWidth: 2,
    borderColor: colors.background,
  },
  content: {
    flex: 1,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  name: {
    ...typography.label,
    color: colors.foreground,
    flex: 1,
  },
  nameBold: {
    fontWeight: '700',
  },
  time: {
    ...typography.caption,
    color: colors.neutral[400],
    marginLeft: spacing.sm,
  },
  timeBold: {
    color: colors.primary.navy,
    fontWeight: '600',
  },
  preview: {
    ...typography.bodySmall,
    color: colors.neutral[500],
    marginTop: 2,
  },
  previewBold: {
    color: colors.foreground,
    fontWeight: '500',
  },
  badge: {
    backgroundColor: colors.primary.gold,
    borderRadius: 12,
    minWidth: 24,
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.primary.navy,
  },
});
