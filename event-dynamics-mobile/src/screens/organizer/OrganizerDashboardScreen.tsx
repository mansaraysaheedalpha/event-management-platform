import React, { useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { Image } from 'expo-image';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import {
  GET_ORGANIZATION_DASHBOARD_STATS_QUERY,
  GET_EVENTS_BY_ORGANIZATION_QUERY,
} from '@/graphql';
import type { DashboardStats, DashboardData } from '@/graphql/dashboard.graphql';
import { Card, Badge, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'OrganizerDashboard'>;

interface OrgEvent {
  id: string;
  name: string;
  status: string;
  startDate: string;
  registrationsCount: number;
  imageUrl?: string;
  eventType?: string;
}

interface EventsResponse {
  eventsByOrganization: {
    totalCount: number;
    events: OrgEvent[];
  };
}

const STATUS_VARIANTS: Record<string, 'success' | 'info' | 'warning' | 'default' | 'destructive'> = {
  LIVE: 'success',
  PUBLISHED: 'info',
  DRAFT: 'warning',
  ENDED: 'default',
  ARCHIVED: 'default',
};

function StatCard({ label, value, change }: { label: string; value: string; change?: number }) {
  return (
    <Card style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {change !== undefined && (
        <Text style={[styles.statChange, change >= 0 ? styles.statPositive : styles.statNegative]}>
          {change >= 0 ? '+' : ''}{change.toFixed(1)}%
        </Text>
      )}
    </Card>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function OrganizerDashboardScreen() {
  const navigation = useNavigation<Nav>();

  const { data: statsData, loading: statsLoading, refetch: refetchStats } =
    useQuery<DashboardData>(GET_ORGANIZATION_DASHBOARD_STATS_QUERY, {
      fetchPolicy: 'cache-and-network',
    });

  const { data: eventsData, loading: eventsLoading, refetch: refetchEvents } =
    useQuery<EventsResponse>(GET_EVENTS_BY_ORGANIZATION_QUERY, {
      variables: { limit: 20, offset: 0, sortBy: 'startDate', sortDirection: 'desc' },
      fetchPolicy: 'cache-and-network',
    });

  const stats = statsData?.organizationDashboardStats;
  const events = eventsData?.eventsByOrganization?.events ?? [];
  const loading = statsLoading || eventsLoading;

  const handleRefresh = useCallback(() => {
    refetchStats();
    refetchEvents();
  }, [refetchStats, refetchEvents]);

  const handleEventPress = useCallback(
    (eventId: string) => {
      navigation.navigate('OrganizerEventDetail', { eventId });
    },
    [navigation],
  );

  const renderEvent = useCallback(
    ({ item }: { item: OrgEvent }) => (
      <TouchableOpacity onPress={() => handleEventPress(item.id)} activeOpacity={0.8}>
        <Card style={styles.eventCard}>
          <View style={styles.eventRow}>
            {item.imageUrl ? (
              <Image
                source={{ uri: item.imageUrl }}
                style={styles.eventImage}
                contentFit="cover"
                placeholder={{ blurhash: imageConfig.defaultBlurhash }}
                cachePolicy={imageConfig.cachePolicy}
                transition={imageConfig.transition}
              />
            ) : (
              <View style={[styles.eventImage, styles.eventImagePlaceholder]}>
                <Text style={styles.eventImageText}>ED</Text>
              </View>
            )}
            <View style={styles.eventInfo}>
              <View style={styles.eventBadgeRow}>
                <Badge
                  variant={STATUS_VARIANTS[item.status] ?? 'default'}
                  label={item.status}
                />
              </View>
              <Text style={styles.eventTitle} numberOfLines={2}>{item.name}</Text>
              <Text style={styles.eventDate}>{formatDate(item.startDate)}</Text>
              <Text style={styles.eventAttendees}>
                {item.registrationsCount} registered
              </Text>
            </View>
          </View>
        </Card>
      </TouchableOpacity>
    ),
    [handleEventPress],
  );

  const listHeader = useMemo(
    () => (
      <View>
        {stats && (
          <View style={styles.statsGrid}>
            <StatCard
              label="Total Events"
              value={String(stats.totalEvents)}
              change={stats.totalEventsChange}
            />
            <StatCard
              label="Attendees"
              value={String(stats.totalAttendees)}
              change={stats.totalAttendeesChange}
            />
            <StatCard
              label="Active Sessions"
              value={String(stats.activeSessions)}
              change={stats.activeSessionsChange}
            />
            <StatCard
              label="Engagement"
              value={`${stats.avgEngagementRate.toFixed(0)}%`}
              change={stats.avgEngagementChange}
            />
          </View>
        )}
        <Text style={styles.sectionHeader}>Your Events</Text>
      </View>
    ),
    [stats],
  );

  if (loading && !statsData && !eventsData) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Organizer Dashboard</Text>
        <Text style={styles.subtitle}>Manage your events</Text>
      </View>

      <FlatList
        data={events}
        renderItem={renderEvent}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No events yet</Text>
            <Text style={styles.emptyText}>Create events on the web dashboard.</Text>
          </View>
        }
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={handleRefresh}
            tintColor={colors.primary.gold}
          />
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 12 },
  title: { ...typography.h1, color: colors.foreground, marginBottom: 4 },
  subtitle: { ...typography.body, color: colors.neutral[500] },
  list: { paddingHorizontal: 24, paddingBottom: 24 },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 8,
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    padding: 16,
    alignItems: 'center',
  },
  statValue: { ...typography.h2, color: colors.foreground, marginBottom: 2 },
  statLabel: { ...typography.caption, color: colors.neutral[500] },
  statChange: { ...typography.caption, marginTop: 4 },
  statPositive: { color: colors.success },
  statNegative: { color: colors.destructive },
  sectionHeader: { ...typography.h3, color: colors.foreground, marginTop: 8, marginBottom: 12 },
  eventCard: { marginBottom: 12, padding: 12 },
  eventRow: { flexDirection: 'row', gap: 12 },
  eventImage: { width: 72, height: 72, borderRadius: 8 },
  eventImagePlaceholder: {
    backgroundColor: colors.primary.navy,
    justifyContent: 'center',
    alignItems: 'center',
  },
  eventImageText: { fontSize: 14, fontWeight: '800', color: colors.primary.gold },
  eventInfo: { flex: 1 },
  eventBadgeRow: { flexDirection: 'row', gap: 6, marginBottom: 4 },
  eventTitle: { ...typography.body, color: colors.foreground, fontWeight: '700', marginBottom: 2 },
  eventDate: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 2 },
  eventAttendees: { ...typography.caption, color: colors.primary.gold, fontWeight: '600' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, marginTop: 40 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
