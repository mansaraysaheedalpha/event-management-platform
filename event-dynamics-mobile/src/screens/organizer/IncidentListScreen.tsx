import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  Modal,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useIncidentManagement } from '@/hooks/useIncidentManagement';
import { Card, Badge, Button, ScreenSkeleton, NotificationRowSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';
import type {
  Incident,
  IncidentSeverity,
  IncidentStatus,
  INCIDENT_TYPE_LABELS,
  INCIDENT_SEVERITY_LABELS,
  INCIDENT_STATUS_LABELS,
} from '@/types/incident';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'IncidentList'>;
type Route = RouteProp<OrganizerStackParamList, 'IncidentList'>;

const SEVERITY_COLORS: Record<IncidentSeverity, string> = {
  LOW: colors.neutral[400],
  MEDIUM: colors.warning,
  HIGH: '#F97316',
  CRITICAL: colors.destructive,
};

const SEVERITY_VARIANTS: Record<IncidentSeverity, 'default' | 'warning' | 'destructive' | 'info'> = {
  LOW: 'default',
  MEDIUM: 'warning',
  HIGH: 'warning',
  CRITICAL: 'destructive',
};

const STATUS_VARIANTS: Record<IncidentStatus, 'default' | 'info' | 'warning' | 'success'> = {
  REPORTED: 'warning',
  ACKNOWLEDGED: 'info',
  INVESTIGATING: 'info',
  RESOLVED: 'success',
};

const TYPE_ICONS: Record<string, string> = {
  HARASSMENT: '🛡️',
  MEDICAL: '🏥',
  TECHNICAL: '🔧',
  SECURITY: '🔒',
  ACCESSIBILITY: '♿',
};

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function IncidentListScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();

  const {
    isConnected,
    isLoading,
    filteredIncidents,
    activeIncidentsCount,
    criticalIncidentsCount,
    acknowledgeIncident,
    startInvestigation,
    resolveIncident,
    isUpdating,
    setFilters,
    clearFilters,
    filters,
  } = useIncidentManagement();

  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'critical' | 'active' | 'resolved'>('all');

  const displayedIncidents = useMemo(() => {
    switch (activeFilter) {
      case 'critical':
        return filteredIncidents.filter((i) => i.severity === 'CRITICAL' && i.status !== 'RESOLVED');
      case 'active':
        return filteredIncidents.filter((i) => i.status !== 'RESOLVED');
      case 'resolved':
        return filteredIncidents.filter((i) => i.status === 'RESOLVED');
      default:
        return filteredIncidents;
    }
  }, [filteredIncidents, activeFilter]);

  const handleAcknowledge = useCallback(
    async (incidentId: string) => {
      await acknowledgeIncident(incidentId);
    },
    [acknowledgeIncident],
  );

  const handleInvestigate = useCallback(
    async (incidentId: string) => {
      await startInvestigation(incidentId);
    },
    [startInvestigation],
  );

  const handleResolve = useCallback(
    async (incidentId: string) => {
      await resolveIncident(incidentId, resolutionNotes || undefined);
      setSelectedIncident(null);
      setResolutionNotes('');
    },
    [resolveIncident, resolutionNotes],
  );

  const renderIncident = useCallback(
    ({ item }: { item: Incident }) => {
      const icon = TYPE_ICONS[item.type] ?? '⚠️';
      return (
        <TouchableOpacity onPress={() => setSelectedIncident(item)} activeOpacity={0.8}>
          <Card
            style={[
              styles.incidentCard,
              item.severity === 'CRITICAL' && item.status !== 'RESOLVED' && styles.incidentCritical,
            ]}
          >
            <View style={styles.incidentHeader}>
              <View style={styles.incidentLeft}>
                <Text style={styles.incidentIcon}>{icon}</Text>
                <Badge variant={SEVERITY_VARIANTS[item.severity]} label={item.severity} />
                <Badge variant={STATUS_VARIANTS[item.status]} label={item.status} />
              </View>
              <Text style={styles.incidentTime}>{formatTimeAgo(item.createdAt)}</Text>
            </View>
            <Text style={styles.incidentDetails} numberOfLines={2}>
              {item.details}
            </Text>
            <Text style={styles.incidentReporter}>
              Reported by {item.reporter.firstName} {item.reporter.lastName}
            </Text>

            {/* Quick actions */}
            {item.status !== 'RESOLVED' && (
              <View style={styles.quickActions}>
                {item.status === 'REPORTED' && (
                  <TouchableOpacity
                    style={styles.quickAction}
                    onPress={() => handleAcknowledge(item.id)}
                  >
                    <Text style={styles.quickActionText}>Acknowledge</Text>
                  </TouchableOpacity>
                )}
                {(item.status === 'REPORTED' || item.status === 'ACKNOWLEDGED') && (
                  <TouchableOpacity
                    style={styles.quickAction}
                    onPress={() => handleInvestigate(item.id)}
                  >
                    <Text style={styles.quickActionText}>Investigate</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  style={[styles.quickAction, styles.resolveAction]}
                  onPress={() => setSelectedIncident(item)}
                >
                  <Text style={[styles.quickActionText, styles.resolveActionText]}>Resolve</Text>
                </TouchableOpacity>
              </View>
            )}
          </Card>
        </TouchableOpacity>
      );
    },
    [handleAcknowledge, handleInvestigate],
  );

  if (isLoading && filteredIncidents.length === 0) {
    return <ScreenSkeleton count={5} ItemSkeleton={NotificationRowSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <View style={styles.headerRight}>
          <View style={[styles.statusDot, isConnected ? styles.dotConnected : styles.dotDisconnected]} />
          {criticalIncidentsCount > 0 && (
            <View style={styles.criticalBadge}>
              <Text style={styles.criticalBadgeText}>{criticalIncidentsCount}</Text>
            </View>
          )}
        </View>
      </View>

      <Text style={styles.title}>Incidents</Text>
      <Text style={styles.subtitle}>
        {activeIncidentsCount} active{criticalIncidentsCount > 0 ? ` (${criticalIncidentsCount} critical)` : ''}
      </Text>

      {/* Filter tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterBar} contentContainerStyle={styles.filterContent}>
        {(['all', 'critical', 'active', 'resolved'] as const).map((filter) => (
          <TouchableOpacity
            key={filter}
            style={[styles.filterChip, activeFilter === filter && styles.filterChipActive]}
            onPress={() => setActiveFilter(filter)}
          >
            <Text style={[styles.filterChipText, activeFilter === filter && styles.filterChipTextActive]}>
              {filter.charAt(0).toUpperCase() + filter.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Incident list */}
      <FlatList
        data={displayedIncidents}
        renderItem={renderIncident}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No incidents</Text>
            <Text style={styles.emptyText}>
              {activeFilter === 'all' ? 'No incidents reported yet.' : `No ${activeFilter} incidents.`}
            </Text>
          </View>
        }
      />

      {/* Resolve modal */}
      <Modal visible={!!selectedIncident && selectedIncident.status !== 'RESOLVED'} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Resolve Incident</Text>
            {selectedIncident && (
              <>
                <Text style={styles.modalDetails}>{selectedIncident.details}</Text>
                <TextInput
                  style={styles.notesInput}
                  placeholder="Resolution notes (optional)..."
                  placeholderTextColor={colors.neutral[500]}
                  value={resolutionNotes}
                  onChangeText={setResolutionNotes}
                  multiline
                  numberOfLines={3}
                />
                <View style={styles.modalActions}>
                  <Button
                    title="Cancel"
                    variant="outline"
                    onPress={() => {
                      setSelectedIncident(null);
                      setResolutionNotes('');
                    }}
                  />
                  <Button
                    title="Resolve"
                    variant="primary"
                    loading={isUpdating}
                    onPress={() => handleResolve(selectedIncident.id)}
                  />
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
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
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  dotConnected: { backgroundColor: colors.success },
  dotDisconnected: { backgroundColor: colors.destructive },
  criticalBadge: {
    backgroundColor: colors.destructive,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  criticalBadgeText: { ...typography.caption, color: '#fff', fontWeight: '700', fontSize: 11 },
  title: { ...typography.h2, color: colors.foreground, paddingHorizontal: 24, paddingTop: 8 },
  subtitle: { ...typography.bodySmall, color: colors.neutral[500], paddingHorizontal: 24, marginBottom: 12 },
  filterBar: { maxHeight: 44, paddingLeft: 24 },
  filterContent: { gap: 8, paddingRight: 24 },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.neutral[800],
  },
  filterChipActive: { backgroundColor: colors.primary.navy },
  filterChipText: { ...typography.caption, color: colors.neutral[400], fontWeight: '600' },
  filterChipTextActive: { color: colors.primary.gold },
  list: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 24 },
  incidentCard: { marginBottom: 12, padding: 14 },
  incidentCritical: { borderColor: colors.destructive, borderWidth: 2 },
  incidentHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  incidentLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  incidentIcon: { fontSize: 16 },
  incidentTime: { ...typography.caption, color: colors.neutral[500] },
  incidentDetails: { ...typography.body, color: colors.foreground, marginBottom: 4 },
  incidentReporter: { ...typography.caption, color: colors.neutral[500], marginBottom: 8 },
  quickActions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  quickAction: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: colors.neutral[700],
  },
  quickActionText: { ...typography.caption, color: colors.neutral[200], fontWeight: '600' },
  resolveAction: { backgroundColor: colors.success },
  resolveActionText: { color: '#fff' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, marginTop: 40 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.background,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: { ...typography.h3, color: colors.foreground, marginBottom: 12 },
  modalDetails: { ...typography.body, color: colors.neutral[400], marginBottom: 16 },
  notesInput: {
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[800],
    borderRadius: 8,
    padding: 12,
    minHeight: 80,
    textAlignVertical: 'top',
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 16,
  },
  modalActions: { flexDirection: 'row', gap: 12, justifyContent: 'flex-end' },
});
