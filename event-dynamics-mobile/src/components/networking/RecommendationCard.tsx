// AI recommendation card component
import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Avatar, Badge, Card } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import type { Recommendation } from '@/types/networking';

interface RecommendationCardProps {
  recommendation: Recommendation;
  onConnect?: (recommendationId: string, userId: string) => void;
  onViewProfile?: (userId: string) => void;
  onPing?: (recommendationId: string, userId: string) => void;
}

export function RecommendationCard({ recommendation, onConnect, onViewProfile, onPing }: RecommendationCardProps) {
  const { user, matchScore, reasons, conversationStarters, connected, pinged } = recommendation;

  const handleConnect = useCallback(() => onConnect?.(recommendation.id, user.id), [recommendation.id, user.id, onConnect]);
  const handleViewProfile = useCallback(() => onViewProfile?.(user.id), [user.id, onViewProfile]);
  const handlePing = useCallback(() => onPing?.(recommendation.id, user.id), [recommendation.id, user.id, onPing]);

  return (
    <Card style={styles.card}>
      <Pressable onPress={handleViewProfile} style={styles.content}>
        <View style={styles.header}>
          <Avatar
            uri={user.avatarUrl ?? undefined}
            name={user.name}
            size={56}
          />
          <View style={styles.info}>
            <Text style={styles.name} numberOfLines={1}>{user.name}</Text>
            {(user.role || user.company) && (
              <Text style={styles.detail} numberOfLines={1}>
                {[user.role, user.company].filter(Boolean).join(' at ')}
              </Text>
            )}
            {user.industry && (
              <Text style={styles.industry} numberOfLines={1}>{user.industry}</Text>
            )}
          </View>
          <View style={styles.scoreContainer}>
            <Text style={styles.scoreValue}>{matchScore}%</Text>
            <Text style={styles.scoreLabel}>match</Text>
          </View>
        </View>

        {reasons.length > 0 && (
          <View style={styles.reasons}>
            {reasons.slice(0, 3).map((reason, i) => (
              <View key={i} style={styles.reasonBadge}>
                <Text style={styles.reasonText}>{reason}</Text>
              </View>
            ))}
          </View>
        )}

        {conversationStarters.length > 0 && (
          <View style={styles.starterContainer}>
            <Text style={styles.starterLabel}>Start a conversation</Text>
            <Text style={styles.starterText} numberOfLines={2}>
              {`\u201C${conversationStarters[0]}\u201D`}
            </Text>
          </View>
        )}

        <View style={styles.actions}>
          {connected ? (
            <Badge label="Connected" variant="success" />
          ) : (
            <Pressable style={styles.connectBtn} onPress={handleConnect}>
              <Text style={styles.connectText}>Connect</Text>
            </Pressable>
          )}
          {!pinged && !connected && (
            <Pressable style={styles.pingBtn} onPress={handlePing}>
              <Text style={styles.pingText}>Ping</Text>
            </Pressable>
          )}
          {pinged && !connected && (
            <Badge label="Pinged" variant="info" />
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
  industry: {
    ...typography.caption,
    color: colors.neutral[400],
    marginTop: 2,
  },
  scoreContainer: {
    alignItems: 'center',
    backgroundColor: colors.primary.gold + '20',
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  scoreValue: {
    ...typography.h3,
    color: colors.primary.goldDark,
  },
  scoreLabel: {
    ...typography.caption,
    color: colors.primary.goldDark,
  },
  reasons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.md,
  },
  reasonBadge: {
    backgroundColor: colors.infoLight,
    borderRadius: 12,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  reasonText: {
    ...typography.caption,
    color: colors.info,
  },
  starterContainer: {
    marginTop: spacing.md,
    backgroundColor: colors.neutral[50],
    borderRadius: 8,
    padding: spacing.sm,
  },
  starterLabel: {
    ...typography.caption,
    color: colors.neutral[400],
    marginBottom: 4,
  },
  starterText: {
    ...typography.bodySmall,
    color: colors.neutral[700],
    fontStyle: 'italic',
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
  connectBtn: {
    backgroundColor: colors.primary.navy,
    borderRadius: 8,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  connectText: {
    ...typography.label,
    color: '#FFFFFF',
  },
  pingBtn: {
    borderWidth: 1,
    borderColor: colors.primary.navy,
    borderRadius: 8,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  pingText: {
    ...typography.label,
    color: colors.primary.navy,
  },
});
