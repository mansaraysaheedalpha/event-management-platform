import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  FlatList,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { GET_EVENT_VIRTUAL_ATTENDANCE_STATS_QUERY } from '@/graphql';
import type { EventVirtualAttendanceStats } from '@/graphql/dashboard.graphql';
import { useLiveDashboard } from '@/hooks/useLiveDashboard';
import { Card, LoadingSpinner } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'LiveMonitor'>;
type Route = RouteProp<OrganizerStackParamList, 'LiveMonitor'>;

interface VirtualStatsResponse {
  eventVirtualAttendanceStats: EventVirtualAttendanceStats;
}

function MetricCard({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  return (
    <Card style={styles.metricCard}>
      <Text style={styles.metricIcon}>{icon}</Text>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </Card>
  );
}

export function LiveMonitorScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { eventId } = route.params;

  const { isConnected, isJoined, dashboardData } = useLiveDashboard(eventId);

  const { data: virtualData } = useQuery<VirtualStatsResponse>(
    GET_EVENT_VIRTUAL_ATTENDANCE_STATS_QUERY,
    {
      variables: { eventId },
      fetchPolicy: 'cache-and-network',
      pollInterval: 30000,
    },
  );

  const virtualStats = virtualData?.eventVirtualAttendanceStats;
  const checkIns = dashboardData?.liveCheckInFeed ?? [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <View style={styles.headerRight}>
          <View style={[styles.statusDot, isConnected ? styles.dotConnected : styles.dotDisconnected]} />
          <Text style={styles.statusText}>{isConnected ? 'Live' : 'Offline'}</Text>
        </View>
      </View>

      <Text style={styles.title}>Live Monitor</Text>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {/* Real-time metrics */}
        <Text style={styles.sectionHeader}>Activity</Text>
        <View style={styles.metricsGrid}>
          <MetricCard
            label="Messages"
            value={dashboardData?.totalMessages ?? '—'}
            icon="💬"
          />
          <MetricCard
            label="Poll Votes"
            value={dashboardData?.totalVotes ?? '—'}
            icon="📊"
          />
          <MetricCard
            label="Questions"
            value={dashboardData?.totalQuestions ?? '—'}
            icon="❓"
          />
          <MetricCard
            label="Upvotes"
            value={dashboardData?.totalUpvotes ?? '—'}
            icon="👍"
          />
          <MetricCard
            label="Reactions"
            value={dashboardData?.totalReactions ?? '—'}
            icon="🎉"
          />
          <MetricCard
            label="Viewers Now"
            value={virtualStats?.currentViewers ?? '—'}
            icon="👁️"
          />
        </View>

        {/* Virtual stats */}
        {virtualStats && (
          <>
            <Text style={styles.sectionHeader}>Virtual Attendance</Text>
            <View style={styles.virtualStats}>
              <Card style={styles.virtualCard}>
                <View style={styles.virtualRow}>
                  <View style={styles.virtualItem}>
                    <Text style={styles.virtualValue}>{virtualStats.totalViews}</Text>
                    <Text style={styles.virtualLabel}>Total Views</Text>
                  </View>
                  <View style={styles.virtualItem}>
                    <Text style={styles.virtualValue}>{virtualStats.uniqueViewers}</Text>
                    <Text style={styles.virtualLabel}>Unique Viewers</Text>
                  </View>
                  <View style={styles.virtualItem}>
                    <Text style={styles.virtualValue}>
                      {Math.round(virtualStats.avgWatchDurationSeconds / 60)}m
                    </Text>
                    <Text style={styles.virtualLabel}>Avg Watch</Text>
                  </View>
                </View>
              </Card>
            </View>
          </>
        )}

        {/* Live check-in feed */}
        <Text style={styles.sectionHeader}>Recent Check-Ins</Text>
        {checkIns.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              {isJoined ? 'No check-ins yet. Waiting for attendees...' : 'Connecting to live feed...'}
            </Text>
          </Card>
        ) : (
          checkIns.slice(0, 10).map((checkIn) => (
            <View key={checkIn.id} style={styles.checkInItem}>
              <View style={styles.checkInDot} />
              <Text style={styles.checkInName}>{checkIn.name}</Text>
              {checkIn.timestamp && (
                <Text style={styles.checkInTime}>
                  {new Date(checkIn.timestamp).toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </Text>
              )}
            </View>
          ))
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 12,
  },
  backText: { ...typography.body, color: colors.primary.gold, fontWeight: '600' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  dotConnected: { backgroundColor: colors.success },
  dotDisconnected: { backgroundColor: colors.destructive },
  statusText: { ...typography.caption, color: colors.neutral[400] },
  title: { ...typography.h2, color: colors.foreground, paddingHorizontal: 24, paddingTop: 8, paddingBottom: 4 },
  content: { paddingHorizontal: 24, paddingBottom: 24 },
  sectionHeader: { ...typography.h4, color: colors.foreground, marginTop: 20, marginBottom: 12 },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  metricCard: {
    width: '30%',
    flexGrow: 1,
    padding: 14,
    alignItems: 'center',
  },
  metricIcon: { fontSize: 20, marginBottom: 4 },
  metricValue: { ...typography.h3, color: colors.foreground },
  metricLabel: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  virtualStats: {},
  virtualCard: { padding: 16 },
  virtualRow: { flexDirection: 'row', justifyContent: 'space-around' },
  virtualItem: { alignItems: 'center' },
  virtualValue: { ...typography.h3, color: colors.primary.gold },
  virtualLabel: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  checkInItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: 10,
  },
  checkInDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.success,
  },
  checkInName: { ...typography.body, color: colors.foreground, flex: 1 },
  checkInTime: { ...typography.caption, color: colors.neutral[400] },
  emptyCard: { padding: 24, alignItems: 'center' },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  bottomSpacer: { height: 40 },
});
