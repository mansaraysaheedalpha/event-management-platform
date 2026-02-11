// Individual leaderboard row with rank medal for top 3

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Avatar } from '@/components/ui/Avatar';
import { colors, typography, spacing } from '@/theme';
import type { LeaderboardEntry } from '@/types/gamification';

interface LeaderboardRowProps {
  entry: LeaderboardEntry;
  isCurrentUser: boolean;
  onPress?: (userId: string) => void;
}

const RANK_MEDALS: Record<number, string> = {
  1: '🥇',
  2: '🥈',
  3: '🥉',
};

export function LeaderboardRow({ entry, isCurrentUser, onPress }: LeaderboardRowProps) {
  const medal = RANK_MEDALS[entry.rank];
  const name = `${entry.user.firstName} ${entry.user.lastName}`;

  return (
    <TouchableOpacity
      style={[styles.row, isCurrentUser && styles.currentUserRow]}
      onPress={() => onPress?.(entry.user.id)}
      activeOpacity={0.7}
      disabled={!onPress}
    >
      <View style={styles.rankContainer}>
        {medal ? (
          <Text style={styles.medal}>{medal}</Text>
        ) : (
          <Text style={styles.rank}>{entry.rank}</Text>
        )}
      </View>

      <Avatar name={name} size={36} />

      <View style={styles.info}>
        <Text style={[styles.name, isCurrentUser && styles.currentUserName]} numberOfLines={1}>
          {name}
          {isCurrentUser ? ' (You)' : ''}
        </Text>
      </View>

      <View style={styles.scoreContainer}>
        <Text style={[styles.score, isCurrentUser && styles.currentUserScore]}>
          {entry.score.toLocaleString()}
        </Text>
        <Text style={styles.scoreLabel}>pts</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    gap: 10,
    borderRadius: 8,
  },
  currentUserRow: {
    backgroundColor: colors.primary.gold + '15',
  },
  rankContainer: {
    width: 28,
    alignItems: 'center',
  },
  medal: {
    fontSize: 20,
  },
  rank: {
    ...typography.body,
    fontWeight: '600',
    color: colors.neutral[500],
  },
  info: {
    flex: 1,
  },
  name: {
    ...typography.body,
    color: colors.foreground,
  },
  currentUserName: {
    fontWeight: '700',
  },
  scoreContainer: {
    alignItems: 'flex-end',
  },
  score: {
    ...typography.body,
    fontWeight: '600',
    color: colors.foreground,
  },
  currentUserScore: {
    color: colors.primary.goldDark,
    fontWeight: '700',
  },
  scoreLabel: {
    ...typography.caption,
    color: colors.neutral[400],
    fontSize: 10,
  },
});
