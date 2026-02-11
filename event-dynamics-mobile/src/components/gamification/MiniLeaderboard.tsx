// Compact leaderboard widget for embedding in EventHub

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Avatar } from '@/components/ui/Avatar';
import { colors, typography, spacing } from '@/theme';
import type { LeaderboardEntry } from '@/types/gamification';

interface MiniLeaderboardProps {
  entries: LeaderboardEntry[];
  currentUserId?: string;
  currentScore: number;
  currentRank: number | null;
  onViewFull?: () => void;
  isLoading?: boolean;
}

const RANK_MEDALS: Record<number, string> = {
  1: '🥇',
  2: '🥈',
  3: '🥉',
};

export function MiniLeaderboard({
  entries,
  currentUserId,
  currentScore,
  currentRank,
  onViewFull,
  isLoading,
}: MiniLeaderboardProps) {
  const top3 = entries.slice(0, 3);
  const isInTop3 = top3.some((e) => e.user.id === currentUserId);

  if (top3.length === 0 && !isLoading) return null;

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={onViewFull}
      activeOpacity={onViewFull ? 0.7 : 1}
      disabled={!onViewFull}
    >
      <View style={styles.header}>
        <Text style={styles.title}>🏆 Leaderboard</Text>
        {onViewFull && <Text style={styles.viewAll}>View All</Text>}
      </View>

      {top3.map((entry) => {
        const isMe = entry.user.id === currentUserId;
        const medal = RANK_MEDALS[entry.rank];
        return (
          <View key={entry.user.id} style={[styles.row, isMe && styles.myRow]}>
            <Text style={styles.rankText}>{medal || `#${entry.rank}`}</Text>
            <Avatar
              name={`${entry.user.firstName} ${entry.user.lastName}`}
              size={24}
            />
            <Text style={[styles.name, isMe && styles.myName]} numberOfLines={1}>
              {isMe ? 'You' : `${entry.user.firstName} ${entry.user.lastName[0]}.`}
            </Text>
            <Text style={[styles.score, isMe && styles.myScore]}>
              {entry.score}
            </Text>
          </View>
        );
      })}

      {!isInTop3 && currentRank && (
        <>
          <Text style={styles.dots}>···</Text>
          <View style={[styles.row, styles.myRow]}>
            <Text style={styles.rankText}>#{currentRank}</Text>
            <Text style={[styles.name, styles.myName]}>You</Text>
            <Text style={[styles.score, styles.myScore]}>
              {currentScore}
            </Text>
          </View>
        </>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  title: {
    ...typography.label,
    fontWeight: '700',
    color: colors.foreground,
  },
  viewAll: {
    ...typography.caption,
    color: colors.primary.gold,
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: 8,
  },
  myRow: {
    backgroundColor: colors.primary.gold + '10',
    borderRadius: 6,
    paddingHorizontal: 6,
  },
  rankText: {
    ...typography.caption,
    fontWeight: '600',
    color: colors.neutral[500],
    width: 28,
    textAlign: 'center',
  },
  name: {
    ...typography.bodySmall,
    color: colors.foreground,
    flex: 1,
  },
  myName: {
    fontWeight: '700',
  },
  score: {
    ...typography.bodySmall,
    fontWeight: '600',
    color: colors.neutral[500],
  },
  myScore: {
    color: colors.primary.goldDark,
    fontWeight: '700',
  },
  dots: {
    ...typography.body,
    color: colors.neutral[300],
    textAlign: 'center',
    letterSpacing: 2,
  },
});
