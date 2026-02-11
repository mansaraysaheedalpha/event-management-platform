// Leaderboard screen — individual and team leaderboards with real-time updates

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import type { HomeStackParamList } from '@/navigation/types';
import { useGamification } from '@/hooks/useGamification';
import { LeaderboardRow } from '@/components/gamification/LeaderboardRow';
import { TeamLeaderboardRow } from '@/components/gamification/TeamLeaderboardRow';
import { GamificationSocketWrapper } from '@/components/gamification/GamificationSocketWrapper';
import { useTeams } from '@/hooks/useTeams';
import { ScreenSkeleton, LeaderboardRowSkeleton } from '@/components/ui';
import { colors, typography, spacing } from '@/theme';
import type { LeaderboardEntry, TeamLeaderboardEntry } from '@/types/gamification';

type Nav = NativeStackNavigationProp<HomeStackParamList, 'Leaderboard'>;
type LeaderboardRoute = RouteProp<HomeStackParamList, 'Leaderboard'>;

type TabKey = 'individual' | 'teams';

function LeaderboardContent() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<LeaderboardRoute>();
  const { eventId } = route.params;
  const gamification = useGamification();
  const teams = useTeams();
  const [activeTab, setActiveTab] = useState<TabKey>('individual');
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    gamification.requestLeaderboard();
    setTimeout(() => setRefreshing(false), 1000);
  }, [gamification.requestLeaderboard]);

  const renderIndividualItem = useCallback(
    ({ item }: { item: LeaderboardEntry }) => (
      <LeaderboardRow
        entry={item}
        isCurrentUser={item.user.id === gamification.currentUserId}
        onPress={(userId) => {
          navigation.navigate('AttendeeProfile', {
            eventId,
            userId,
          });
        }}
      />
    ),
    [gamification.currentUserId, navigation]
  );

  const renderTeamItem = useCallback(
    ({ item }: { item: TeamLeaderboardEntry }) => (
      <TeamLeaderboardRow
        entry={item}
        isCurrentTeam={item.teamId === teams.currentTeam?.id}
      />
    ),
    [teams.currentTeam?.id]
  );

  const keyExtractorIndividual = useCallback(
    (item: LeaderboardEntry) => item.user.id,
    []
  );
  const keyExtractorTeam = useCallback(
    (item: TeamLeaderboardEntry) => item.teamId,
    []
  );

  if (gamification.isLoadingLeaderboard && gamification.leaderboard.length === 0) {
    return <ScreenSkeleton count={10} ItemSkeleton={LeaderboardRowSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Leaderboard</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Score Card */}
      <View style={styles.scoreCard}>
        <View style={styles.scoreInfo}>
          <Text style={styles.scoreValue}>
            {gamification.currentScore.toLocaleString()}
          </Text>
          <Text style={styles.scoreLabel}>Your Points</Text>
        </View>
        {gamification.currentRank && (
          <View style={styles.rankBadge}>
            <Text style={styles.rankValue}>#{gamification.currentRank}</Text>
            <Text style={styles.rankLabel}>Rank</Text>
          </View>
        )}
      </View>

      {/* Tab Switcher */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'individual' && styles.activeTab]}
          onPress={() => setActiveTab('individual')}
        >
          <Text style={[styles.tabText, activeTab === 'individual' && styles.activeTabText]}>
            Individual
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'teams' && styles.activeTab]}
          onPress={() => setActiveTab('teams')}
        >
          <Text style={[styles.tabText, activeTab === 'teams' && styles.activeTabText]}>
            Teams
          </Text>
        </TouchableOpacity>
      </View>

      {/* List */}
      {activeTab === 'individual' ? (
        <FlashList
          data={gamification.leaderboard}
          renderItem={renderIndividualItem}
          keyExtractor={keyExtractorIndividual}
          estimatedItemSize={64}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.primary.gold}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>🏆</Text>
              <Text style={styles.emptyText}>No participants yet</Text>
              <Text style={styles.emptySubtext}>Be the first to earn points!</Text>
            </View>
          }
        />
      ) : (
        <FlashList
          data={gamification.teamLeaderboard}
          renderItem={renderTeamItem}
          keyExtractor={keyExtractorTeam}
          estimatedItemSize={64}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.primary.gold}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>👥</Text>
              <Text style={styles.emptyText}>No teams yet</Text>
              <Text style={styles.emptySubtext}>Create or join a team to compete!</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

export function LeaderboardScreen() {
  const route = useRoute<LeaderboardRoute>();
  const { eventId, sessionId } = route.params;

  return (
    <GamificationSocketWrapper sessionId={sessionId} eventId={eventId}>
      <LeaderboardContent />
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
  scoreCard: {
    flexDirection: 'row',
    backgroundColor: colors.primary.navy,
    marginHorizontal: spacing.base,
    borderRadius: 16,
    padding: spacing.lg,
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.base,
  },
  scoreInfo: {
    gap: 2,
  },
  scoreValue: {
    ...typography.h1,
    color: colors.primary.gold,
    fontWeight: '700',
  },
  scoreLabel: {
    ...typography.caption,
    color: colors.primary.gold,
    opacity: 0.7,
  },
  rankBadge: {
    backgroundColor: colors.primary.gold + '20',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: 12,
    alignItems: 'center',
  },
  rankValue: {
    ...typography.h2,
    color: colors.primary.gold,
    fontWeight: '700',
  },
  rankLabel: {
    ...typography.caption,
    color: colors.primary.gold,
    opacity: 0.7,
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
    ...typography.label,
    color: colors.neutral[500],
  },
  activeTabText: {
    color: colors.foreground,
    fontWeight: '600',
  },
  list: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing['2xl'],
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
  },
});
