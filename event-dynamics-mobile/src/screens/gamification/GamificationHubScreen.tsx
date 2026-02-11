// Gamification Hub — tabbed view with Progress, Achievements, Leaderboard

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import type { HomeStackParamList } from '@/navigation/types';
import { useGamification } from '@/hooks/useGamification';
import { useTeams } from '@/hooks/useTeams';
import { AnimatedCounter } from '@/components/gamification/AnimatedCounter';
import { StreakIndicator } from '@/components/gamification/StreakIndicator';
import { AchievementCard } from '@/components/gamification/AchievementCard';
import { LeaderboardRow } from '@/components/gamification/LeaderboardRow';
import { TeamLeaderboardRow } from '@/components/gamification/TeamLeaderboardRow';
import { GamificationSocketWrapper } from '@/components/gamification/GamificationSocketWrapper';
import { LoadingSpinner } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import { POINT_VALUES, REASON_EMOJI, REASON_TEXT, PointReason, ACHIEVEMENT_CATEGORIES } from '@/types/gamification';

type Nav = NativeStackNavigationProp<HomeStackParamList, 'GamificationHub'>;
type HubRoute = RouteProp<HomeStackParamList, 'GamificationHub'>;

type TabKey = 'progress' | 'achievements' | 'leaderboard';

function GamificationHubContent() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<HubRoute>();
  const { eventId } = route.params;
  const gamification = useGamification();
  const teams = useTeams();
  const [activeTab, setActiveTab] = useState<TabKey>('progress');
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    gamification.requestLeaderboard();
    gamification.requestAchievements();
    gamification.requestUserStats();
    setTimeout(() => setRefreshing(false), 1000);
  }, [gamification.requestLeaderboard, gamification.requestAchievements, gamification.requestUserStats]);

  const renderProgressTab = () => {
    const unlockedCount = gamification.achievementProgress.filter((a) => a.isUnlocked).length;
    const totalCount = gamification.achievementProgress.length;

    // Find next 3 closest achievements
    const nextAchievements = gamification.achievementProgress
      .filter((a) => !a.isUnlocked)
      .sort((a, b) => b.percentage - a.percentage)
      .slice(0, 3);

    return (
      <>
        {/* Score & Streak */}
        <View style={styles.statsCard}>
          <View style={styles.statRow}>
            <View style={styles.statItem}>
              <AnimatedCounter
                value={gamification.currentScore}
                style={styles.bigScore}
              />
              <Text style={styles.statLabel}>Total Points</Text>
            </View>
            {gamification.currentRank && (
              <View style={styles.statItem}>
                <Text style={styles.bigRank}>#{gamification.currentRank}</Text>
                <Text style={styles.statLabel}>Rank</Text>
              </View>
            )}
          </View>

          <StreakIndicator streak={gamification.streak} />
        </View>

        {/* Achievement Overview */}
        <View style={styles.overviewCard}>
          <Text style={styles.cardTitle}>
            Achievements ({unlockedCount}/{totalCount})
          </Text>
          <View style={styles.overviewBar}>
            <View
              style={[
                styles.overviewFill,
                {
                  width: totalCount > 0
                    ? `${(unlockedCount / totalCount) * 100}%`
                    : '0%',
                },
              ]}
            />
          </View>
        </View>

        {/* Next Achievements */}
        {nextAchievements.length > 0 && (
          <View style={styles.nextSection}>
            <Text style={styles.cardTitle}>Next Achievements</Text>
            <View style={styles.nextGrid}>
              {nextAchievements.map((a) => (
                <View key={a.key} style={styles.nextItem}>
                  <AchievementCard achievement={a} />
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Recent Activity */}
        {gamification.recentPointEvents.length > 0 && (
          <View style={styles.activitySection}>
            <Text style={styles.cardTitle}>Recent Activity</Text>
            {gamification.recentPointEvents.slice(-5).reverse().map((e) => (
              <View key={e.id} style={styles.activityRow}>
                <Text style={styles.activityEmoji}>
                  {gamification.getReasonEmoji(e.reason)}
                </Text>
                <Text style={styles.activityText}>
                  {gamification.getReasonText(e.reason)}
                </Text>
                <Text style={styles.activityPoints}>+{e.points}</Text>
              </View>
            ))}
          </View>
        )}

        {/* How to Earn Points */}
        <View style={styles.earnSection}>
          <Text style={styles.cardTitle}>How to Earn Points</Text>
          {Object.entries(POINT_VALUES).map(([reason, pts]) => (
            <View key={reason} style={styles.earnRow}>
              <Text style={styles.earnEmoji}>
                {REASON_EMOJI[reason as PointReason]}
              </Text>
              <Text style={styles.earnText}>
                {REASON_TEXT[reason as PointReason]}
              </Text>
              <Text style={styles.earnPoints}>+{pts} pt{pts !== 1 ? 's' : ''}</Text>
            </View>
          ))}
        </View>
      </>
    );
  };

  const renderAchievementsTab = () => {
    const grouped: Record<string, typeof gamification.achievementProgress> = {};
    for (const ap of gamification.achievementProgress) {
      const cat = ap.category || 'Other';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(ap);
    }

    return (
      <>
        {ACHIEVEMENT_CATEGORIES.map((cat) => {
          const items = grouped[cat.key];
          if (!items || items.length === 0) return null;
          return (
            <View key={cat.key} style={styles.categorySection}>
              <View style={styles.categoryHeader}>
                <Text style={styles.categoryIcon}>{cat.icon}</Text>
                <Text style={styles.categoryLabel}>{cat.label}</Text>
                <Text style={styles.categoryCount}>
                  {items.filter((i) => i.isUnlocked).length}/{items.length}
                </Text>
              </View>
              <View style={styles.grid}>
                {items.map((item) => (
                  <View key={item.key} style={styles.gridItem}>
                    <AchievementCard achievement={item} />
                  </View>
                ))}
              </View>
            </View>
          );
        })}

        {gamification.achievementProgress.length === 0 && (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>🏅</Text>
            <Text style={styles.emptyText}>No achievements available</Text>
          </View>
        )}
      </>
    );
  };

  const renderLeaderboardTab = () => (
    <>
      {/* Individual */}
      <Text style={styles.cardTitle}>Individual Rankings</Text>
      {gamification.leaderboard.length > 0 ? (
        gamification.leaderboard.map((entry) => (
          <LeaderboardRow
            key={entry.user.id}
            entry={entry}
            isCurrentUser={entry.user.id === gamification.currentUserId}
            onPress={(userId) =>
              navigation.navigate('AttendeeProfile', { eventId, userId })
            }
          />
        ))
      ) : (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyText}>No participants yet</Text>
        </View>
      )}

      {/* Team */}
      {gamification.teamLeaderboard.length > 0 && (
        <>
          <Text style={[styles.cardTitle, styles.teamTitle]}>Team Rankings</Text>
          {gamification.teamLeaderboard.map((entry) => (
            <TeamLeaderboardRow
              key={entry.teamId}
              entry={entry}
              isCurrentTeam={entry.teamId === teams.currentTeam?.id}
            />
          ))}
        </>
      )}
    </>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Gamification</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {(['progress', 'achievements', 'leaderboard'] as const).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.activeTab]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.activeTabText]}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary.gold}
          />
        }
      >
        {activeTab === 'progress' && renderProgressTab()}
        {activeTab === 'achievements' && renderAchievementsTab()}
        {activeTab === 'leaderboard' && renderLeaderboardTab()}
      </ScrollView>
    </SafeAreaView>
  );
}

export function GamificationHubScreen() {
  const route = useRoute<HubRoute>();
  const { eventId, sessionId } = route.params;

  return (
    <GamificationSocketWrapper sessionId={sessionId} eventId={eventId}>
      <GamificationHubContent />
    </GamificationSocketWrapper>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  backText: {
    fontSize: 24,
    color: colors.foreground,
  },
  title: {
    ...typography.h3,
    color: colors.foreground,
  },
  tabs: {
    flexDirection: 'row',
    marginHorizontal: spacing.base,
    backgroundColor: colors.neutral[100],
    borderRadius: 10,
    padding: 3,
    marginBottom: spacing.md,
  },
  tab: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    borderRadius: 8,
  },
  activeTab: {
    backgroundColor: colors.card,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  tabText: {
    ...typography.caption,
    color: colors.neutral[500],
    fontWeight: '500',
  },
  activeTabText: {
    color: colors.foreground,
    fontWeight: '600',
  },
  content: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing['3xl'],
  },
  statsCard: {
    backgroundColor: colors.primary.navy,
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.base,
    gap: spacing.md,
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  statItem: {
    alignItems: 'center',
    gap: 2,
  },
  bigScore: {
    ...typography.h1,
    color: colors.primary.gold,
    fontWeight: '700',
  },
  bigRank: {
    ...typography.h1,
    color: colors.primary.gold,
    fontWeight: '700',
  },
  statLabel: {
    ...typography.caption,
    color: colors.primary.gold,
    opacity: 0.7,
  },
  overviewCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  cardTitle: {
    ...typography.h4,
    color: colors.foreground,
    marginBottom: spacing.md,
  },
  overviewBar: {
    height: 8,
    backgroundColor: colors.neutral[200],
    borderRadius: 4,
    overflow: 'hidden',
  },
  overviewFill: {
    height: '100%',
    backgroundColor: colors.primary.gold,
    borderRadius: 4,
  },
  nextSection: {
    marginBottom: spacing.base,
  },
  nextGrid: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  nextItem: {
    flex: 1,
  },
  activitySection: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  activityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: 4,
  },
  activityEmoji: {
    fontSize: 16,
  },
  activityText: {
    ...typography.bodySmall,
    color: colors.foreground,
    flex: 1,
  },
  activityPoints: {
    ...typography.bodySmall,
    fontWeight: '700',
    color: colors.success,
  },
  earnSection: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  earnRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: 4,
  },
  earnEmoji: {
    fontSize: 16,
    width: 24,
    textAlign: 'center',
  },
  earnText: {
    ...typography.bodySmall,
    color: colors.foreground,
    flex: 1,
  },
  earnPoints: {
    ...typography.bodySmall,
    fontWeight: '600',
    color: colors.primary.goldDark,
  },
  categorySection: {
    marginBottom: spacing.xl,
  },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  categoryIcon: {
    fontSize: 18,
  },
  categoryLabel: {
    ...typography.h4,
    color: colors.foreground,
    flex: 1,
  },
  categoryCount: {
    ...typography.caption,
    color: colors.neutral[400],
    fontWeight: '600',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  gridItem: {
    width: '31%',
    flexGrow: 1,
    maxWidth: '33%',
  },
  teamTitle: {
    marginTop: spacing.xl,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing['2xl'],
    gap: spacing.sm,
  },
  emptyIcon: {
    fontSize: 48,
  },
  emptyText: {
    ...typography.body,
    color: colors.neutral[500],
  },
});
