import React, { useEffect, useState, useCallback } from 'react';
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
import { useLeads } from '@/hooks/useLeads';
import { Card, Badge, Button, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'SponsorDashboard'>;
type Route = RouteProp<SponsorStackParamList, 'SponsorDashboard'>;

export function SponsorDashboardScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId, sponsorName } = route.params;

  const {
    leads,
    stats,
    isLoading,
    isLoadingStats,
    isRealTimeConnected,
    refetch,
  } = useLeads({ sponsorId });

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    refetch();
    setRefreshing(false);
  }, [refetch]);

  const recentLeads = leads.slice(0, 5);

  if (isLoading && !stats) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary.gold} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>
          <View style={styles.headerInfo}>
            <Text style={styles.headerTitle}>{sponsorName}</Text>
            {isRealTimeConnected && (
              <View style={styles.liveBadge}>
                <View style={styles.liveDot} />
                <Text style={styles.liveText}>Real-time</Text>
              </View>
            )}
          </View>
        </View>

        <View style={styles.content}>
          {/* Stats cards */}
          <View style={styles.statsGrid}>
            <Card style={styles.statCard}>
              <Text style={styles.statNumber}>
                {isLoadingStats ? '...' : stats?.total_leads ?? 0}
              </Text>
              <Text style={styles.statLabel}>Total Leads</Text>
            </Card>
            <Card style={[styles.statCard, { borderLeftColor: colors.destructive, borderLeftWidth: 2 }]}>
              <Text style={[styles.statNumber, { color: colors.destructive }]}>
                {isLoadingStats ? '...' : stats?.hot_leads ?? 0}
              </Text>
              <Text style={styles.statLabel}>Hot</Text>
            </Card>
            <Card style={[styles.statCard, { borderLeftColor: colors.warning, borderLeftWidth: 2 }]}>
              <Text style={[styles.statNumber, { color: colors.warning }]}>
                {isLoadingStats ? '...' : stats?.warm_leads ?? 0}
              </Text>
              <Text style={styles.statLabel}>Warm</Text>
            </Card>
            <Card style={[styles.statCard, { borderLeftColor: colors.info, borderLeftWidth: 2 }]}>
              <Text style={[styles.statNumber, { color: colors.info }]}>
                {isLoadingStats ? '...' : stats?.cold_leads ?? 0}
              </Text>
              <Text style={styles.statLabel}>Cold</Text>
            </Card>
          </View>

          {/* Conversion stats */}
          {stats && (
            <Card style={styles.conversionCard}>
              <View style={styles.conversionRow}>
                <View style={styles.conversionItem}>
                  <Text style={styles.conversionNumber}>{stats.leads_contacted}</Text>
                  <Text style={styles.conversionLabel}>Contacted</Text>
                </View>
                <View style={styles.conversionItem}>
                  <Text style={styles.conversionNumber}>{stats.leads_converted}</Text>
                  <Text style={styles.conversionLabel}>Converted</Text>
                </View>
                <View style={styles.conversionItem}>
                  <Text style={[styles.conversionNumber, { color: colors.success }]}>
                    {(stats.conversion_rate * 100).toFixed(1)}%
                  </Text>
                  <Text style={styles.conversionLabel}>Rate</Text>
                </View>
              </View>
            </Card>
          )}

          {/* Quick actions */}
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.actionsGrid}>
            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => navigation.navigate('LeadCapture', { sponsorId, eventId })}
            >
              <Text style={styles.actionIcon}>QR</Text>
              <Text style={styles.actionText}>Scan Lead</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => navigation.navigate('LeadList', { sponsorId, eventId })}
            >
              <Text style={styles.actionIcon}>LIST</Text>
              <Text style={styles.actionText}>All Leads</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => navigation.navigate('SponsorAnalytics', { sponsorId, eventId })}
            >
              <Text style={styles.actionIcon}>STAT</Text>
              <Text style={styles.actionText}>Analytics</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => navigation.navigate('SponsorMessages', { sponsorId, eventId })}
            >
              <Text style={styles.actionIcon}>MSG</Text>
              <Text style={styles.actionText}>Messages</Text>
            </TouchableOpacity>
          </View>

          {/* Recent leads */}
          {recentLeads.length > 0 && (
            <>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>Recent Leads</Text>
                <TouchableOpacity
                  onPress={() => navigation.navigate('LeadList', { sponsorId, eventId })}
                >
                  <Text style={styles.seeAllText}>See All</Text>
                </TouchableOpacity>
              </View>
              {recentLeads.map((lead) => (
                <TouchableOpacity
                  key={lead.id}
                  onPress={() =>
                    navigation.navigate('LeadDetail', { sponsorId, eventId, leadId: lead.id })
                  }
                >
                  <Card style={styles.leadCard}>
                    <View style={styles.leadRow}>
                      <View style={styles.leadInfo}>
                        <Text style={styles.leadName}>
                          {lead.user_name || 'Unknown'}
                        </Text>
                        {lead.user_company && (
                          <Text style={styles.leadCompany}>{lead.user_company}</Text>
                        )}
                      </View>
                      <Badge
                        variant={
                          lead.intent_level === 'hot'
                            ? 'destructive'
                            : lead.intent_level === 'warm'
                              ? 'warning'
                              : 'info'
                        }
                        label={lead.intent_level.toUpperCase()}
                      />
                    </View>
                  </Card>
                </TouchableOpacity>
              ))}
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backText: { ...typography.label, color: colors.primary.gold, marginBottom: 8 },
  headerInfo: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerTitle: { ...typography.h2, color: colors.foreground },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success },
  liveText: { ...typography.caption, color: colors.success },
  content: { padding: 16 },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  statCard: { flex: 1, minWidth: '45%', padding: 14, alignItems: 'center' },
  statNumber: { ...typography.h2, color: colors.primary.gold },
  statLabel: { ...typography.caption, color: colors.neutral[500], marginTop: 4 },
  conversionCard: { padding: 16, marginTop: 12 },
  conversionRow: { flexDirection: 'row', justifyContent: 'space-around' },
  conversionItem: { alignItems: 'center' },
  conversionNumber: { ...typography.h3, color: colors.foreground },
  conversionLabel: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  sectionTitle: {
    ...typography.h4,
    color: colors.foreground,
    marginTop: 24,
    marginBottom: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 24,
    marginBottom: 12,
  },
  seeAllText: { ...typography.label, color: colors.primary.gold },
  actionsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  actionCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: colors.neutral[50],
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionIcon: {
    ...typography.h3,
    color: colors.primary.gold,
    marginBottom: 6,
  },
  actionText: { ...typography.bodySmall, color: colors.foreground, fontWeight: '600' },
  leadCard: { padding: 12, marginBottom: 8 },
  leadRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  leadInfo: { flex: 1 },
  leadName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  leadCompany: { ...typography.bodySmall, color: colors.neutral[500] },
});
