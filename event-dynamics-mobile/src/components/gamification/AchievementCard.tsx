// Achievement card — locked/unlocked states with progress bar

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, spacing } from '@/theme';
import type { AchievementProgress } from '@/types/gamification';

interface AchievementCardProps {
  achievement: AchievementProgress;
}

export function AchievementCard({ achievement }: AchievementCardProps) {
  return (
    <View style={[styles.card, achievement.isUnlocked && styles.unlockedCard]}>
      <View style={styles.iconContainer}>
        <Text style={styles.icon}>
          {achievement.isUnlocked ? achievement.icon : '🔒'}
        </Text>
      </View>

      <Text
        style={[styles.name, !achievement.isUnlocked && styles.lockedName]}
        numberOfLines={2}
      >
        {achievement.badgeName}
      </Text>

      {achievement.isUnlocked ? (
        <Text style={styles.unlocked}>Unlocked</Text>
      ) : (
        <View style={styles.progressContainer}>
          <View style={styles.progressBar}>
            <View
              style={[
                styles.progressFill,
                { width: `${Math.min(achievement.percentage, 100)}%` },
              ]}
            />
          </View>
          <Text style={styles.progressText}>
            {achievement.current}/{achievement.target}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    borderRadius: 12,
    padding: spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 120,
    justifyContent: 'center',
  },
  unlockedCard: {
    backgroundColor: colors.primary.gold + '10',
    borderColor: colors.primary.gold + '40',
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.neutral[100],
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  icon: {
    fontSize: 22,
  },
  name: {
    ...typography.caption,
    fontWeight: '600',
    color: colors.foreground,
    textAlign: 'center',
    marginBottom: 4,
  },
  lockedName: {
    color: colors.neutral[400],
  },
  unlocked: {
    ...typography.caption,
    color: colors.success,
    fontWeight: '600',
    fontSize: 10,
  },
  progressContainer: {
    width: '100%',
    alignItems: 'center',
    gap: 2,
  },
  progressBar: {
    width: '100%',
    height: 4,
    backgroundColor: colors.neutral[200],
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.primary.gold,
    borderRadius: 2,
  },
  progressText: {
    ...typography.caption,
    color: colors.neutral[400],
    fontSize: 10,
  },
});
