import React, { useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useLeads } from '@/hooks/useLeads';
import { Card, Badge, ScreenSkeleton, AttendeeRowSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';
import type { Lead } from '@/types/leads';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'LeadList'>;
type Route = RouteProp<SponsorStackParamList, 'LeadList'>;

type IntentFilter = 'all' | 'hot' | 'warm' | 'cold';

const LEAD_STATUS_COLORS: Record<string, string> = {
  new: colors.info,
  contacted: colors.warning,
  qualified: colors.success,
  not_interested: colors.neutral[400],
  converted: '#8B5CF6',
};

const LeadRow = React.memo(function LeadRow({
  lead,
  onPress,
  onToggleStar,
}: {
  lead: Lead;
  onPress: () => void;
  onToggleStar: () => void;
}) {

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
      <Card style={styles.leadCard}>
        <View style={styles.leadHeader}>
          <View style={styles.leadInfo}>
            <Text style={styles.leadName}>{lead.user_name || 'Unknown'}</Text>
            {lead.user_company && (
              <Text style={styles.leadCompany}>{lead.user_company}</Text>
            )}
            {lead.user_title && (
              <Text style={styles.leadTitle}>{lead.user_title}</Text>
            )}
          </View>
          <TouchableOpacity onPress={onToggleStar} style={styles.starBtn}>
            <Text style={styles.starIcon}>{lead.is_starred ? '\u2605' : '\u2606'}</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.leadFooter}>
          <Badge
            variant={
              lead.intent_level === 'hot'
                ? 'destructive'
                : lead.intent_level === 'warm'
                  ? 'warning'
                  : 'info'
            }
            label={`${lead.intent_level.toUpperCase()} (${lead.intent_score})`}
          />
          <View
            style={[
              styles.statusDot,
              { backgroundColor: LEAD_STATUS_COLORS[lead.follow_up_status] || colors.neutral[400] },
            ]}
          />
          <Text style={styles.statusText}>
            {lead.follow_up_status.replace(/_/g, ' ')}
          </Text>
          <Text style={styles.leadDate}>
            {new Date(lead.last_interaction_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
            })}
          </Text>
        </View>
      </Card>
    </TouchableOpacity>
  );
});

export function LeadListScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId } = route.params;

  const {
    leads,
    stats,
    isLoading,
    hasNextPage,
    fetchNextPage,
    refetch,
    updateLead,
  } = useLeads({ sponsorId });

  const [searchQuery, setSearchQuery] = useState('');
  const [intentFilter, setIntentFilter] = useState<IntentFilter>('all');
  const [refreshing, setRefreshing] = useState(false);

  const filteredLeads = useMemo(() => {
    let filtered = leads;
    if (intentFilter !== 'all') {
      filtered = filtered.filter((l) => l.intent_level === intentFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (l) =>
          l.user_name?.toLowerCase().includes(q) ||
          l.user_email?.toLowerCase().includes(q) ||
          l.user_company?.toLowerCase().includes(q),
      );
    }
    return filtered;
  }, [leads, intentFilter, searchQuery]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const handleToggleStar = useCallback(
    (lead: Lead) => {
      updateLead(lead.id, { is_starred: !lead.is_starred });
    },
    [updateLead],
  );

  if (isLoading && leads.length === 0) {
    return <ScreenSkeleton count={6} ItemSkeleton={AttendeeRowSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>
          Leads {stats ? `(${stats.total_leads})` : ''}
        </Text>
        <TouchableOpacity
          onPress={() => navigation.navigate('LeadCapture', { sponsorId, eventId })}
        >
          <Text style={styles.addText}>+ Add</Text>
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search leads..."
          placeholderTextColor={colors.neutral[400]}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Filter tabs */}
      <View style={styles.filterRow}>
        {(['all', 'hot', 'warm', 'cold'] as IntentFilter[]).map((filter) => (
          <TouchableOpacity
            key={filter}
            style={[styles.filterChip, intentFilter === filter && styles.filterChipActive]}
            onPress={() => setIntentFilter(filter)}
          >
            <Text
              style={[
                styles.filterChipText,
                intentFilter === filter && styles.filterChipTextActive,
              ]}
            >
              {filter === 'all' ? 'All' : filter.charAt(0).toUpperCase() + filter.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Lead list */}
      <FlatList
        data={filteredLeads}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <LeadRow
            lead={item}
            onPress={() =>
              navigation.navigate('LeadDetail', { sponsorId, eventId, leadId: item.id })
            }
            onToggleStar={() => handleToggleStar(item)}
          />
        )}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary.gold} />
        }
        onEndReached={() => {
          if (hasNextPage) fetchNextPage();
        }}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No leads yet</Text>
            <Text style={styles.emptySubtitle}>
              Capture leads by scanning QR codes or adding them manually
            </Text>
          </View>
        }
      />
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
  addText: { ...typography.label, color: colors.primary.gold },
  searchContainer: { paddingHorizontal: 16, paddingTop: 12 },
  searchInput: {
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[100],
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.neutral[100],
  },
  filterChipActive: { backgroundColor: colors.primary.gold },
  filterChipText: { ...typography.bodySmall, color: colors.neutral[600], fontWeight: '500' },
  filterChipTextActive: { color: colors.primary.navy },
  listContent: { padding: 16 },
  leadCard: { padding: 14, marginBottom: 10 },
  leadHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  leadInfo: { flex: 1 },
  leadName: { ...typography.body, color: colors.foreground, fontWeight: '700' },
  leadCompany: { ...typography.bodySmall, color: colors.neutral[500] },
  leadTitle: { ...typography.caption, color: colors.neutral[400] },
  starBtn: { padding: 4 },
  starIcon: { fontSize: 20, color: colors.primary.gold },
  leadFooter: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { ...typography.caption, color: colors.neutral[500], textTransform: 'capitalize' },
  leadDate: { ...typography.caption, color: colors.neutral[400], marginLeft: 'auto' },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptySubtitle: { ...typography.body, color: colors.neutral[400], textAlign: 'center' },
});
