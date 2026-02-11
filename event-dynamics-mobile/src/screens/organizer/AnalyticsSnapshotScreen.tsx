import React, { useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import Svg, { Rect } from 'react-native-svg';
import {
  GET_EVENT_TICKET_SUMMARY_QUERY,
  GET_ENGAGEMENT_BREAKDOWN_QUERY,
  GET_WEEKLY_ATTENDANCE_QUERY,
} from '@/graphql';
import type { EngagementBreakdown, AttendanceDataPoint } from '@/graphql/dashboard.graphql';
import { Card, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'AnalyticsSnapshot'>;
type Route = RouteProp<OrganizerStackParamList, 'AnalyticsSnapshot'>;

interface TicketTypeStat {
  ticketTypeId: string;
  ticketTypeName: string;
  quantitySold: number;
  quantityAvailable: number;
  revenue: { amount: number; currency: string; formatted: string };
  percentageSold: number;
}

interface TicketSummary {
  eventId: string;
  totalTicketTypes: number;
  totalCapacity: number;
  totalSold: number;
  totalRevenue: { amount: number; currency: string; formatted: string };
  ticketTypeStats: TicketTypeStat[];
  salesToday: number;
  salesThisWeek: number;
  salesThisMonth: number;
  revenueToday: { formatted: string };
  revenueThisWeek: { formatted: string };
  revenueThisMonth: { formatted: string };
}

interface TicketSummaryResponse {
  eventTicketSummary: TicketSummary;
}

interface EngagementResponse {
  engagementBreakdown: EngagementBreakdown;
}

interface WeeklyAttendanceResponse {
  weeklyAttendance: { data: AttendanceDataPoint[] };
}

function MetricCard({ label, value, sublabel }: { label: string; value: string; sublabel?: string }) {
  return (
    <Card style={styles.metricCard}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
      {sublabel && <Text style={styles.metricSublabel}>{sublabel}</Text>}
    </Card>
  );
}

function ProgressBar({ percent, color }: { percent: number; color: string }) {
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <View style={styles.progressBarBg}>
      <View style={[styles.progressBarFill, { width: `${clamped}%`, backgroundColor: color }]} />
    </View>
  );
}

function SimpleBarChart({ data }: { data: AttendanceDataPoint[] }) {
  if (data.length === 0) return null;
  const maxVal = Math.max(...data.map((d) => d.value), 1);
  const barWidth = 28;
  const chartHeight = 120;
  const gap = 8;
  const totalWidth = data.length * (barWidth + gap);

  return (
    <View style={styles.chartContainer}>
      <Svg width={totalWidth} height={chartHeight + 20}>
        {data.map((d, i) => {
          const barHeight = (d.value / maxVal) * chartHeight;
          const x = i * (barWidth + gap);
          const y = chartHeight - barHeight;
          return (
            <React.Fragment key={d.date}>
              <Rect
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                rx={4}
                fill={colors.primary.gold}
              />
            </React.Fragment>
          );
        })}
      </Svg>
      <View style={[styles.chartLabels, { width: totalWidth }]}>
        {data.map((d, i) => (
          <Text key={d.date} style={[styles.chartLabel, { width: barWidth + gap }]}>
            {d.label}
          </Text>
        ))}
      </View>
    </View>
  );
}

export function AnalyticsSnapshotScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { eventId } = route.params;

  const {
    data: ticketData,
    loading: ticketLoading,
    refetch: refetchTickets,
  } = useQuery<TicketSummaryResponse>(GET_EVENT_TICKET_SUMMARY_QUERY, {
    variables: { eventId },
    fetchPolicy: 'cache-and-network',
  });

  const {
    data: engagementData,
    loading: engagementLoading,
    refetch: refetchEngagement,
  } = useQuery<EngagementResponse>(GET_ENGAGEMENT_BREAKDOWN_QUERY, {
    variables: { eventId },
    fetchPolicy: 'cache-and-network',
  });

  const {
    data: attendanceData,
    loading: attendanceLoading,
    refetch: refetchAttendance,
  } = useQuery<WeeklyAttendanceResponse>(GET_WEEKLY_ATTENDANCE_QUERY, {
    variables: { days: 7 },
    fetchPolicy: 'cache-and-network',
  });

  const loading = ticketLoading || engagementLoading || attendanceLoading;
  const summary = ticketData?.eventTicketSummary;
  const engagement = engagementData?.engagementBreakdown;
  const attendance = attendanceData?.weeklyAttendance?.data ?? [];

  const checkInRate = useMemo(() => {
    if (!summary || summary.totalSold === 0) return 0;
    // Check-in rate approximated from ticket stats
    return Math.round((summary.salesToday / Math.max(summary.totalSold, 1)) * 100);
  }, [summary]);

  const handleRefresh = useCallback(() => {
    refetchTickets();
    refetchEngagement();
    refetchAttendance();
  }, [refetchTickets, refetchEngagement, refetchAttendance]);

  if (loading && !ticketData && !engagementData) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={handleRefresh} tintColor={colors.primary.gold} />
        }
      >
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>

        <Text style={styles.title}>Analytics</Text>

        {/* Key metrics */}
        {summary && (
          <>
            <View style={styles.metricsGrid}>
              <MetricCard label="Total Sold" value={String(summary.totalSold)} />
              <MetricCard label="Revenue" value={summary.totalRevenue.formatted} />
              <MetricCard label="Today" value={String(summary.salesToday)} sublabel={summary.revenueToday.formatted} />
              <MetricCard label="This Week" value={String(summary.salesThisWeek)} sublabel={summary.revenueThisWeek.formatted} />
            </View>

            {/* Ticket breakdown */}
            <Text style={styles.sectionHeader}>Tickets by Type</Text>
            {summary.ticketTypeStats.map((stat) => (
              <View key={stat.ticketTypeId} style={styles.ticketRow}>
                <View style={styles.ticketInfo}>
                  <Text style={styles.ticketName}>{stat.ticketTypeName}</Text>
                  <Text style={styles.ticketCount}>
                    {stat.quantitySold} sold · {stat.revenue.formatted}
                  </Text>
                </View>
                <View style={styles.ticketProgress}>
                  <ProgressBar percent={stat.percentageSold} color={colors.primary.gold} />
                  <Text style={styles.ticketPercent}>{stat.percentageSold.toFixed(0)}%</Text>
                </View>
              </View>
            ))}
          </>
        )}

        {/* Engagement breakdown */}
        {engagement && (
          <>
            <Text style={styles.sectionHeader}>Engagement</Text>
            <Card style={styles.engagementCard}>
              <View style={styles.engagementRow}>
                <Text style={styles.engagementLabel}>Q&A Participation</Text>
                <View style={styles.engagementRight}>
                  <ProgressBar percent={engagement.qaParticipation} color={colors.info} />
                  <Text style={styles.engagementPercent}>{engagement.qaParticipation.toFixed(0)}%</Text>
                </View>
              </View>
              <View style={styles.engagementRow}>
                <Text style={styles.engagementLabel}>Poll Response Rate</Text>
                <View style={styles.engagementRight}>
                  <ProgressBar percent={engagement.pollResponseRate} color={colors.warning} />
                  <Text style={styles.engagementPercent}>{engagement.pollResponseRate.toFixed(0)}%</Text>
                </View>
              </View>
              <View style={styles.engagementRow}>
                <Text style={styles.engagementLabel}>Chat Activity</Text>
                <View style={styles.engagementRight}>
                  <ProgressBar percent={engagement.chatActivityRate} color={colors.success} />
                  <Text style={styles.engagementPercent}>{engagement.chatActivityRate.toFixed(0)}%</Text>
                </View>
              </View>
            </Card>
          </>
        )}

        {/* Weekly attendance chart */}
        {attendance.length > 0 && (
          <>
            <Text style={styles.sectionHeader}>Weekly Attendance</Text>
            <Card style={styles.chartCard}>
              <SimpleBarChart data={attendance} />
            </Card>
          </>
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  backButton: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 4 },
  backText: { ...typography.body, color: colors.primary.gold, fontWeight: '600' },
  title: { ...typography.h2, color: colors.foreground, paddingHorizontal: 24, paddingTop: 8, paddingBottom: 4 },
  sectionHeader: {
    ...typography.h4,
    color: colors.foreground,
    paddingHorizontal: 24,
    marginTop: 24,
    marginBottom: 12,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    paddingHorizontal: 24,
    marginTop: 16,
  },
  metricCard: {
    flex: 1,
    minWidth: '45%',
    padding: 16,
    alignItems: 'center',
  },
  metricValue: { ...typography.h3, color: colors.primary.gold },
  metricLabel: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  metricSublabel: { ...typography.caption, color: colors.neutral[400], marginTop: 2 },
  ticketRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  ticketInfo: { flex: 1 },
  ticketName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  ticketCount: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  ticketProgress: { width: 100, alignItems: 'flex-end', gap: 4 },
  ticketPercent: { ...typography.caption, color: colors.neutral[400] },
  progressBarBg: {
    width: '100%',
    height: 6,
    backgroundColor: colors.neutral[700],
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: { height: '100%', borderRadius: 3 },
  engagementCard: { marginHorizontal: 24, padding: 16, gap: 14 },
  engagementRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  engagementLabel: { ...typography.bodySmall, color: colors.foreground, flex: 1 },
  engagementRight: { width: 120, flexDirection: 'row', alignItems: 'center', gap: 8 },
  engagementPercent: { ...typography.caption, color: colors.neutral[400], width: 32, textAlign: 'right' },
  chartCard: { marginHorizontal: 24, padding: 16 },
  chartContainer: { alignItems: 'center' },
  chartLabels: { flexDirection: 'row', marginTop: 4 },
  chartLabel: { ...typography.caption, color: colors.neutral[500], textAlign: 'center', fontSize: 10 },
  bottomSpacer: { height: 40 },
});
