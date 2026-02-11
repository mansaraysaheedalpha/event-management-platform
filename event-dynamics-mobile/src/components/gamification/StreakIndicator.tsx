// Streak indicator with fire emoji and multiplier badge

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, spacing } from '@/theme';
import type { StreakInfo } from '@/types/gamification';

interface StreakIndicatorProps {
  streak: StreakInfo;
  compact?: boolean;
}

export function StreakIndicator({ streak, compact = false }: StreakIndicatorProps) {
  if (!streak.active) return null;

  if (compact) {
    return (
      <View style={styles.compactContainer}>
        <Text style={styles.fireEmoji}>🔥</Text>
        <Text style={styles.compactText}>{streak.multiplier}x</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.fireEmoji}>🔥</Text>
      <View style={styles.info}>
        <Text style={styles.streakCount}>
          {streak.count} streak{streak.count !== 1 ? 's' : ''}
        </Text>
        <Text style={styles.multiplier}>{streak.multiplier}x multiplier</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF6B35' + '15',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 12,
    gap: spacing.sm,
  },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  fireEmoji: {
    fontSize: 18,
  },
  info: {
    flex: 1,
  },
  streakCount: {
    ...typography.bodySmall,
    fontWeight: '600',
    color: '#FF6B35',
  },
  multiplier: {
    ...typography.caption,
    color: colors.neutral[500],
  },
  compactText: {
    ...typography.caption,
    fontWeight: '700',
    color: '#FF6B35',
  },
});
