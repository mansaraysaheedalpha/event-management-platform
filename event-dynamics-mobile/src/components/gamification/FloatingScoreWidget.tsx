// Floating score widget — shows current score + rank, tap to open hub

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, typography, spacing } from '@/theme';
import type { StreakInfo } from '@/types/gamification';

interface FloatingScoreWidgetProps {
  currentScore: number;
  currentRank: number | null;
  streak: StreakInfo;
  onPress?: () => void;
}

export function FloatingScoreWidget({
  currentScore,
  currentRank,
  streak,
  onPress,
}: FloatingScoreWidgetProps) {
  if (currentScore === 0 && !currentRank) return null;

  return (
    <TouchableOpacity style={styles.widget} onPress={onPress} activeOpacity={0.85}>
      <View style={styles.scoreSection}>
        <Text style={styles.score}>{currentScore.toLocaleString()}</Text>
        <Text style={styles.scoreLabel}>pts</Text>
      </View>

      {currentRank && (
        <View style={styles.rankBadge}>
          <Text style={styles.rankText}>#{currentRank}</Text>
        </View>
      )}

      {streak.active && (
        <View style={styles.streakBadge}>
          <Text style={styles.streakEmoji}>🔥</Text>
          <Text style={styles.streakText}>{streak.multiplier}x</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  widget: {
    position: 'absolute',
    bottom: 16,
    left: 16,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary.navy,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 24,
    gap: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
    zIndex: 40,
  },
  scoreSection: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 3,
  },
  score: {
    ...typography.body,
    color: colors.primary.gold,
    fontWeight: '700',
    fontSize: 18,
  },
  scoreLabel: {
    ...typography.caption,
    color: colors.primary.gold,
    opacity: 0.7,
    fontSize: 11,
  },
  rankBadge: {
    backgroundColor: colors.primary.gold + '25',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  rankText: {
    ...typography.caption,
    color: colors.primary.gold,
    fontWeight: '700',
    fontSize: 11,
  },
  streakBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  streakEmoji: {
    fontSize: 12,
  },
  streakText: {
    ...typography.caption,
    color: '#FF6B35',
    fontWeight: '700',
    fontSize: 11,
  },
});
