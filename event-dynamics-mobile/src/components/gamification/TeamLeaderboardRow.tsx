// Team leaderboard row

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography } from '@/theme';
import type { TeamLeaderboardEntry } from '@/types/gamification';

interface TeamLeaderboardRowProps {
  entry: TeamLeaderboardEntry;
  isCurrentTeam: boolean;
}

const RANK_MEDALS: Record<number, string> = {
  1: '🥇',
  2: '🥈',
  3: '🥉',
};

export function TeamLeaderboardRow({ entry, isCurrentTeam }: TeamLeaderboardRowProps) {
  const medal = RANK_MEDALS[entry.rank];

  return (
    <View style={[styles.row, isCurrentTeam && styles.currentTeamRow]}>
      <View style={styles.rankContainer}>
        {medal ? (
          <Text style={styles.medal}>{medal}</Text>
        ) : (
          <Text style={styles.rank}>{entry.rank}</Text>
        )}
      </View>

      <View style={styles.teamIcon}>
        <Text style={styles.teamEmoji}>👥</Text>
      </View>

      <View style={styles.info}>
        <Text style={[styles.name, isCurrentTeam && styles.currentTeamName]} numberOfLines={1}>
          {entry.name}
          {isCurrentTeam ? ' (Your Team)' : ''}
        </Text>
        <Text style={styles.members}>
          {entry.memberCount} {entry.memberCount === 1 ? 'member' : 'members'}
        </Text>
      </View>

      <View style={styles.scoreContainer}>
        <Text style={[styles.score, isCurrentTeam && styles.currentTeamScore]}>
          {entry.score.toLocaleString()}
        </Text>
        <Text style={styles.scoreLabel}>pts</Text>
      </View>
    </View>
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
  currentTeamRow: {
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
  teamIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primary.navy,
    justifyContent: 'center',
    alignItems: 'center',
  },
  teamEmoji: {
    fontSize: 18,
  },
  info: {
    flex: 1,
  },
  name: {
    ...typography.body,
    color: colors.foreground,
  },
  currentTeamName: {
    fontWeight: '700',
  },
  members: {
    ...typography.caption,
    color: colors.neutral[500],
  },
  scoreContainer: {
    alignItems: 'flex-end',
  },
  score: {
    ...typography.body,
    fontWeight: '600',
    color: colors.foreground,
  },
  currentTeamScore: {
    color: colors.primary.goldDark,
    fontWeight: '700',
  },
  scoreLabel: {
    ...typography.caption,
    color: colors.neutral[400],
    fontSize: 10,
  },
});
