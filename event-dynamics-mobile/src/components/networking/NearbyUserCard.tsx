// Nearby user card for proximity networking
import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Avatar, Badge } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import type { NearbyUser } from '@/types/networking';
import { formatDistanceText } from '@/types/networking';

interface NearbyUserCardProps {
  user: NearbyUser;
  onPing?: (userId: string) => void;
  onViewProfile?: (userId: string) => void;
}

export function NearbyUserCard({ user, onPing, onViewProfile }: NearbyUserCardProps) {
  const handlePing = useCallback(() => onPing?.(user.id), [user.id, onPing]);
  const handlePress = useCallback(() => onViewProfile?.(user.id), [user.id, onViewProfile]);

  return (
    <Pressable onPress={handlePress} style={styles.container}>
      <View style={styles.avatarWrap}>
        <Avatar uri={user.avatarUrl ?? undefined} name={user.name} size={44} />
        {user.matchScore != null && user.matchScore > 0 && (
          <View style={styles.scoreBadge}>
            <Text style={styles.scoreText}>{user.matchScore}%</Text>
          </View>
        )}
      </View>

      <View style={styles.info}>
        <View style={styles.nameRow}>
          <Text style={styles.name} numberOfLines={1}>{user.name}</Text>
          {user.alreadyConnected && <Badge label="Connected" variant="success" />}
        </View>
        <Text style={styles.distance}>{formatDistanceText(user.distance)}</Text>
        {user.sharedInterests && user.sharedInterests.length > 0 && (
          <View style={styles.interests}>
            {user.sharedInterests.slice(0, 3).map((interest, i) => (
              <View key={i} style={styles.interestBadge}>
                <Text style={styles.interestText}>{interest}</Text>
              </View>
            ))}
          </View>
        )}
      </View>

      <Pressable
        style={[styles.pingBtn, user.alreadyConnected && styles.pingBtnMuted]}
        onPress={handlePing}
      >
        <Text style={[styles.pingText, user.alreadyConnected && styles.pingTextMuted]}>
          {user.alreadyConnected ? 'Wave' : 'Ping'}
        </Text>
      </Pressable>
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
  avatarWrap: {
    position: 'relative',
  },
  scoreBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: colors.primary.gold,
    borderRadius: 8,
    paddingHorizontal: 4,
    paddingVertical: 1,
    minWidth: 24,
    alignItems: 'center',
  },
  scoreText: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.primary.navy,
  },
  info: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  name: {
    ...typography.label,
    color: colors.foreground,
    flex: 1,
  },
  distance: {
    ...typography.caption,
    color: colors.neutral[400],
    marginTop: 2,
  },
  interests: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginTop: spacing.xs,
  },
  interestBadge: {
    backgroundColor: colors.neutral[100],
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  interestText: {
    fontSize: 10,
    color: colors.neutral[500],
  },
  pingBtn: {
    backgroundColor: colors.primary.navy,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  pingBtnMuted: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: colors.neutral[300],
  },
  pingText: {
    ...typography.label,
    color: '#FFFFFF',
    fontSize: 13,
  },
  pingTextMuted: {
    color: colors.neutral[500],
  },
});
