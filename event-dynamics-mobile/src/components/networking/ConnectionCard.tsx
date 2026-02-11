// Connection card component for displaying a user connection
import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Avatar, Badge, Card } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import type { Connection, ConnectionUser } from '@/types/networking';
import { getOtherUser, getStrengthLabel, getConnectionTypeLabel } from '@/types/networking';

interface ConnectionCardProps {
  connection: Connection;
  currentUserId: string;
  onPress?: (connection: Connection) => void;
  onMessage?: (userId: string, userName: string) => void;
  onFollowUp?: (connectionId: string) => void;
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w ago`;
}

function strengthColor(strength: string): 'success' | 'warning' | 'default' {
  switch (strength) {
    case 'STRONG': return 'success';
    case 'MODERATE': return 'warning';
    default: return 'default';
  }
}

export function ConnectionCard({ connection, currentUserId, onPress, onMessage, onFollowUp }: ConnectionCardProps) {
  const otherUser = getOtherUser(connection, currentUserId);
  const fullName = `${otherUser.firstName} ${otherUser.lastName}`;

  const handlePress = useCallback(() => onPress?.(connection), [connection, onPress]);
  const handleMessage = useCallback(() => onMessage?.(otherUser.id, fullName), [otherUser.id, fullName, onMessage]);
  const handleFollowUp = useCallback(() => onFollowUp?.(connection.id), [connection.id, onFollowUp]);

  return (
    <Card style={styles.card}>
      <Pressable onPress={handlePress} style={styles.content}>
        <View style={styles.header}>
          <Avatar
            uri={otherUser.avatarUrl ?? undefined}
            name={fullName}
            size={48}
          />
          <View style={styles.info}>
            <Text style={styles.name} numberOfLines={1}>{fullName}</Text>
            {(otherUser.role || otherUser.company) && (
              <Text style={styles.detail} numberOfLines={1}>
                {[otherUser.role, otherUser.company].filter(Boolean).join(' at ')}
              </Text>
            )}
            <View style={styles.badges}>
              <Badge label={getStrengthLabel(connection.strength)} variant={strengthColor(connection.strength)} />
              <Text style={styles.time}>{timeAgo(connection.createdAt)}</Text>
            </View>
          </View>
        </View>

        {connection.initialMessage && (
          <Text style={styles.message} numberOfLines={2}>
            {`\u201C${connection.initialMessage}\u201D`}
          </Text>
        )}

        {connection.contexts.length > 0 && (
          <View style={styles.contexts}>
            {connection.contexts.slice(0, 2).map((ctx, i) => (
              <View key={i} style={styles.contextBadge}>
                <Text style={styles.contextText}>{ctx.contextValue}</Text>
              </View>
            ))}
            {connection.contexts.length > 2 && (
              <Text style={styles.moreContexts}>+{connection.contexts.length - 2} more</Text>
            )}
          </View>
        )}

        <View style={styles.actions}>
          <Pressable style={styles.actionBtn} onPress={handleMessage}>
            <Text style={styles.actionText}>Message</Text>
          </Pressable>
          {!connection.followUpSent && (
            <Pressable style={[styles.actionBtn, styles.followUpBtn]} onPress={handleFollowUp}>
              <Text style={[styles.actionText, styles.followUpText]}>Follow Up</Text>
            </Pressable>
          )}
          {connection.followUpSent && (
            <Badge label="Followed up" variant="success" />
          )}
        </View>
      </Pressable>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    marginBottom: spacing.sm,
  },
  content: {
    padding: spacing.base,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  info: {
    flex: 1,
  },
  name: {
    ...typography.h4,
    color: colors.foreground,
  },
  detail: {
    ...typography.bodySmall,
    color: colors.neutral[500],
    marginTop: 2,
  },
  badges: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  time: {
    ...typography.caption,
    color: colors.neutral[400],
  },
  message: {
    ...typography.bodySmall,
    color: colors.neutral[600],
    fontStyle: 'italic',
    marginTop: spacing.sm,
    paddingLeft: spacing.xs,
  },
  contexts: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  contextBadge: {
    backgroundColor: colors.neutral[100],
    borderRadius: 12,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  contextText: {
    ...typography.caption,
    color: colors.neutral[600],
  },
  moreContexts: {
    ...typography.caption,
    color: colors.neutral[400],
    alignSelf: 'center',
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  actionBtn: {
    borderWidth: 1,
    borderColor: colors.primary.navy,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  actionText: {
    ...typography.label,
    color: colors.primary.navy,
  },
  followUpBtn: {
    backgroundColor: colors.primary.gold,
    borderColor: colors.primary.gold,
  },
  followUpText: {
    color: colors.primary.navy,
  },
});
