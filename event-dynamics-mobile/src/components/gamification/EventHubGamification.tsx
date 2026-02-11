// Gamification section for EventHub — wraps itself in SessionSocketProvider
// Shows mini leaderboard, floating score widget, achievement toasts, and quick actions

import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SessionSocketProvider } from '@/context/SessionSocketContext';
import { useGamification } from '@/hooks/useGamification';
import { MiniLeaderboard } from './MiniLeaderboard';
import { PointsToast } from './PointsToast';
import { FloatingScoreWidget } from './FloatingScoreWidget';
import { AchievementUnlockModal } from './AchievementUnlockModal';
import { colors, typography, spacing } from '@/theme';
import type { Achievement } from '@/types/gamification';

interface GamificationWidgetProps {
  onOpenHub: () => void;
  onOpenLeaderboard: () => void;
  onOpenAchievements: () => void;
  onOpenTeams: () => void;
}

function GamificationWidget({
  onOpenHub,
  onOpenLeaderboard,
  onOpenAchievements,
  onOpenTeams,
}: GamificationWidgetProps) {
  const gamification = useGamification();
  const [celebratingAchievement, setCelebratingAchievement] = useState<Achievement | null>(null);

  // Watch for new achievement unlocks
  const latestAchievement = gamification.achievements[gamification.achievements.length - 1];
  React.useEffect(() => {
    if (latestAchievement && !celebratingAchievement) {
      setCelebratingAchievement(latestAchievement);
    }
  }, [latestAchievement, celebratingAchievement]);

  const handleDismissAchievement = useCallback(() => {
    if (celebratingAchievement) {
      gamification.clearRecentAchievements([
        celebratingAchievement.id || celebratingAchievement.badgeName,
      ]);
    }
    setCelebratingAchievement(null);
  }, [celebratingAchievement, gamification.clearRecentAchievements]);

  return (
    <>
      {/* Quick Action Buttons */}
      <View style={styles.quickActions}>
        <TouchableOpacity style={styles.actionBtn} onPress={onOpenLeaderboard}>
          <Text style={styles.actionIcon}>🏆</Text>
          <Text style={styles.actionLabel}>Leaderboard</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={onOpenAchievements}>
          <Text style={styles.actionIcon}>🏅</Text>
          <Text style={styles.actionLabel}>Achievements</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={onOpenTeams}>
          <Text style={styles.actionIcon}>👥</Text>
          <Text style={styles.actionLabel}>Teams</Text>
        </TouchableOpacity>
      </View>

      {/* Mini Leaderboard */}
      <MiniLeaderboard
        entries={gamification.leaderboard}
        currentUserId={gamification.currentUserId}
        currentScore={gamification.currentScore}
        currentRank={gamification.currentRank}
        onViewFull={onOpenLeaderboard}
        isLoading={gamification.isLoadingLeaderboard}
      />

      {/* Points Toast Overlay */}
      <PointsToast events={gamification.recentPointEvents} />

      {/* Floating Score Widget */}
      <FloatingScoreWidget
        currentScore={gamification.currentScore}
        currentRank={gamification.currentRank}
        streak={gamification.streak}
        onPress={onOpenHub}
      />

      {/* Achievement Unlock Modal */}
      <AchievementUnlockModal
        achievement={celebratingAchievement}
        onDismiss={handleDismissAchievement}
      />
    </>
  );
}

interface EventHubGamificationProps {
  sessionId: string;
  eventId: string;
  onOpenHub: () => void;
  onOpenLeaderboard: () => void;
  onOpenAchievements: () => void;
  onOpenTeams: () => void;
}

export function EventHubGamification({
  sessionId,
  eventId,
  onOpenHub,
  onOpenLeaderboard,
  onOpenAchievements,
  onOpenTeams,
}: EventHubGamificationProps) {
  if (!sessionId) {
    // No active session — show static quick actions only
    return (
      <View style={styles.quickActions}>
        <View style={styles.noSessionBanner}>
          <Text style={styles.noSessionText}>
            Gamification activates when a session is live
          </Text>
        </View>
      </View>
    );
  }

  return (
    <SessionSocketProvider sessionId={sessionId} eventId={eventId}>
      <GamificationWidget
        onOpenHub={onOpenHub}
        onOpenLeaderboard={onOpenLeaderboard}
        onOpenAchievements={onOpenAchievements}
        onOpenTeams={onOpenTeams}
      />
    </SessionSocketProvider>
  );
}

const styles = StyleSheet.create({
  quickActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.base,
  },
  actionBtn: {
    flex: 1,
    backgroundColor: colors.primary.navy,
    borderRadius: 12,
    paddingVertical: spacing.md,
    alignItems: 'center',
    gap: 4,
  },
  actionIcon: {
    fontSize: 20,
  },
  actionLabel: {
    ...typography.caption,
    color: colors.primary.gold,
    fontWeight: '600',
  },
  noSessionBanner: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    borderRadius: 12,
    padding: spacing.base,
    alignItems: 'center',
  },
  noSessionText: {
    ...typography.bodySmall,
    color: colors.neutral[400],
    textAlign: 'center',
  },
});
