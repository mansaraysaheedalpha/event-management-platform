import React, { useState, useEffect, useCallback } from 'react';
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
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';
import { Card, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';
import type { BoothAnalytics } from '@/types/expo';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'SponsorAnalytics'>;
type Route = RouteProp<SponsorStackParamList, 'SponsorAnalytics'>;

function StatCard({
  title,
  value,
  subtitle,
  color,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}) {
  return (
    <Card style={styles.statCard}>
      <Text style={[styles.statValue, color ? { color } : undefined]}>{value}</Text>
      <Text style={styles.statTitle}>{title}</Text>
      {subtitle && <Text style={styles.statSubtitle}>{subtitle}</Text>}
    </Card>
  );
}

function BarChart({
  data,
  label,
}: {
  data: Record<string, number>;
  label: string;
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;

  const maxVal = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <View style={styles.chartContainer}>
      <Text style={styles.chartLabel}>{label}</Text>
      {entries.map(([name, count]) => (
        <View key={name} style={styles.barRow}>
          <Text style={styles.barLabel} numberOfLines={1}>
            {name}
          </Text>
          <View style={styles.barTrack}>
            <View
              style={[
                styles.barFill,
                { width: `${(count / maxVal) * 100}%` },
              ]}
            />
          </View>
          <Text style={styles.barValue}>{count}</Text>
        </View>
      ))}
    </View>
  );
}

export function SponsorAnalyticsScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId } = route.params;

  const { token } = useAuthStore();
  const [analytics, setAnalytics] = useState<BoothAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAnalytics = useCallback(async () => {
    if (!token) return;

    setError(null);
    try {
      const response = await fetch(
        `${env.EVENT_SERVICE_URL}/sponsors/sponsors/${sponsorId}/analytics`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        },
      );

      if (!response.ok) throw new Error(`Failed: ${response.status}`);

      const data: BoothAnalytics = await response.json();
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setIsLoading(false);
    }
  }, [token, sponsorId]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchAnalytics();
    setRefreshing(false);
  }, [fetchAnalytics]);

  if (isLoading) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Analytics</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary.gold} />
        }
      >
        {error && (
          <Card style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        )}

        {analytics && (
          <>
            {/* Visitor stats */}
            <Text style={styles.sectionTitle}>Booth Visitors</Text>
            <View style={styles.statsRow}>
              <StatCard title="Current" value={analytics.currentVisitors} color={colors.success} />
              <StatCard title="Total" value={analytics.totalVisitors} />
              <StatCard title="Unique" value={analytics.uniqueVisitors} />
            </View>
            <View style={styles.statsRow}>
              <StatCard title="Peak" value={analytics.peakVisitors} color={colors.warning} />
              <StatCard
                title="Avg. Duration"
                value={`${Math.round(analytics.avgVisitDuration / 60)}m`}
              />
            </View>

            {/* Engagement stats */}
            <Text style={styles.sectionTitle}>Engagement</Text>
            <View style={styles.statsRow}>
              <StatCard title="Chat Messages" value={analytics.totalChatMessages} />
              <StatCard title="Video Sessions" value={analytics.totalVideoSessions} />
            </View>
            <View style={styles.statsRow}>
              <StatCard title="Downloads" value={analytics.totalDownloads} />
              <StatCard title="CTA Clicks" value={analytics.totalCtaClicks} />
              <StatCard title="Leads" value={analytics.totalLeads} color={colors.primary.gold} />
            </View>

            {/* Resource downloads chart */}
            {Object.keys(analytics.resourceDownloads).length > 0 && (
              <BarChart data={analytics.resourceDownloads} label="Downloads by Resource" />
            )}

            {/* CTA clicks chart */}
            {Object.keys(analytics.ctaClicks).length > 0 && (
              <BarChart data={analytics.ctaClicks} label="CTA Clicks" />
            )}
          </>
        )}

        {!analytics && !error && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No analytics data available yet</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backText: { ...typography.label, color: colors.primary.gold },
  headerTitle: { ...typography.h4, color: colors.foreground },
  content: { padding: 16, paddingBottom: 40 },
  sectionTitle: {
    ...typography.h4,
    color: colors.foreground,
    marginTop: 20,
    marginBottom: 10,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 10,
  },
  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  statCard: { flex: 1, padding: 14, alignItems: 'center' },
  statValue: { ...typography.h2, color: colors.primary.gold },
  statTitle: { ...typography.caption, color: colors.neutral[500], marginTop: 4 },
  statSubtitle: { ...typography.caption, color: colors.neutral[400], marginTop: 2 },
  errorCard: { padding: 12, backgroundColor: colors.destructiveLight },
  errorText: { ...typography.bodySmall, color: colors.destructive },
  chartContainer: { marginTop: 20 },
  chartLabel: { ...typography.h4, color: colors.foreground, marginBottom: 10 },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  barLabel: { ...typography.caption, color: colors.neutral[600], width: 80 },
  barTrack: {
    flex: 1,
    height: 20,
    backgroundColor: colors.neutral[100],
    borderRadius: 4,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: colors.primary.gold,
    borderRadius: 4,
  },
  barValue: { ...typography.caption, color: colors.neutral[600], width: 30, textAlign: 'right' },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { ...typography.body, color: colors.neutral[400] },
});
