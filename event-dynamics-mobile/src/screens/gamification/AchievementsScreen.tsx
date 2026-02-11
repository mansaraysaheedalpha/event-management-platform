// Achievements screen — grid of all achievements organized by category

import React, { useMemo } from 'react';
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
import type { RouteProp } from '@react-navigation/native';
import type { HomeStackParamList } from '@/navigation/types';
import { useGamification } from '@/hooks/useGamification';
import { AchievementCard } from '@/components/gamification/AchievementCard';
import { GamificationSocketWrapper } from '@/components/gamification/GamificationSocketWrapper';
import { ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import { ACHIEVEMENT_CATEGORIES } from '@/types/gamification';
import type { AchievementProgress } from '@/types/gamification';

type AchievementsRoute = RouteProp<HomeStackParamList, 'Achievements'>;

function AchievementsContent() {
  const navigation = useNavigation();
  const gamification = useGamification();
  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = React.useCallback(() => {
    setRefreshing(true);
    gamification.requestAchievements();
    setTimeout(() => setRefreshing(false), 1000);
  }, [gamification.requestAchievements]);

  // Group achievements by category
  const grouped = useMemo(() => {
    const groups: Record<string, AchievementProgress[]> = {};
    for (const ap of gamification.achievementProgress) {
      const cat = ap.category || 'Other';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(ap);
    }
    return groups;
  }, [gamification.achievementProgress]);

  const unlockedCount = gamification.achievementProgress.filter((a) => a.isUnlocked).length;
  const totalCount = gamification.achievementProgress.length;

  if (gamification.achievementProgress.length === 0 && !gamification.isJoined) {
    return <ScreenSkeleton count={6} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Achievements</Text>
        <View style={styles.backBtn} />
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
        {/* Summary */}
        <View style={styles.summary}>
          <View style={styles.summaryLeft}>
            <Text style={styles.summaryCount}>
              {unlockedCount}/{totalCount}
            </Text>
            <Text style={styles.summaryLabel}>Unlocked</Text>
          </View>
          <View style={styles.summaryBar}>
            <View
              style={[
                styles.summaryFill,
                {
                  width: totalCount > 0
                    ? `${(unlockedCount / totalCount) * 100}%`
                    : '0%',
                },
              ]}
            />
          </View>
        </View>

        {/* Categories */}
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
            <Text style={styles.emptySubtext}>
              Achievements will appear when a session is live
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

export function AchievementsScreen() {
  const route = useRoute<AchievementsRoute>();
  const { eventId, sessionId } = route.params;

  return (
    <GamificationSocketWrapper sessionId={sessionId} eventId={eventId}>
      <AchievementsContent />
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
  content: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing['3xl'],
  },
  summary: {
    backgroundColor: colors.primary.navy,
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.xl,
  },
  summaryLeft: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  summaryCount: {
    ...typography.h2,
    color: colors.primary.gold,
    fontWeight: '700',
  },
  summaryLabel: {
    ...typography.bodySmall,
    color: colors.primary.gold,
    opacity: 0.7,
  },
  summaryBar: {
    height: 6,
    backgroundColor: colors.primary.navyLight,
    borderRadius: 3,
    overflow: 'hidden',
  },
  summaryFill: {
    height: '100%',
    backgroundColor: colors.primary.gold,
    borderRadius: 3,
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
  emptyContainer: {
    alignItems: 'center',
    paddingTop: spacing['4xl'],
    gap: spacing.sm,
  },
  emptyIcon: {
    fontSize: 48,
  },
  emptyText: {
    ...typography.h4,
    color: colors.foreground,
  },
  emptySubtext: {
    ...typography.bodySmall,
    color: colors.neutral[500],
    textAlign: 'center',
  },
});
