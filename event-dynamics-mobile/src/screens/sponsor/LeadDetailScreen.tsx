import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useLeads } from '@/hooks/useLeads';
import { Card, Badge, Button, Input } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'LeadDetail'>;
type Route = RouteProp<SponsorStackParamList, 'LeadDetail'>;

const FOLLOW_UP_STATUSES = [
  { value: 'new', label: 'New', color: colors.info },
  { value: 'contacted', label: 'Contacted', color: colors.warning },
  { value: 'qualified', label: 'Qualified', color: colors.success },
  { value: 'not_interested', label: 'Not Interested', color: colors.neutral[400] },
  { value: 'converted', label: 'Converted', color: '#8B5CF6' },
] as const;

export function LeadDetailScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId, leadId } = route.params;

  const { leads, updateLead } = useLeads({ sponsorId });

  const lead = useMemo(() => leads.find((l) => l.id === leadId), [leads, leadId]);

  const [followUpNotes, setFollowUpNotes] = useState(lead?.follow_up_notes || '');
  const [contactNotes, setContactNotes] = useState(lead?.contact_notes || '');
  const [isSaving, setIsSaving] = useState(false);

  // Sync local state when lead updates from store/socket (but not while user is editing)
  useEffect(() => {
    if (!isSaving && lead) {
      setFollowUpNotes(lead.follow_up_notes || '');
      setContactNotes(lead.contact_notes || '');
    }
  }, [lead?.follow_up_notes, lead?.contact_notes, isSaving]);

  const handleStatusChange = useCallback(
    async (status: string) => {
      if (!lead) return;
      try {
        await updateLead(lead.id, {
          follow_up_status: status as typeof lead.follow_up_status,
        });
      } catch {
        Alert.alert('Error', 'Failed to update status');
      }
    },
    [lead, updateLead],
  );

  const handleToggleStar = useCallback(async () => {
    if (!lead) return;
    try {
      await updateLead(lead.id, { is_starred: !lead.is_starred });
    } catch {
      Alert.alert('Error', 'Failed to update');
    }
  }, [lead, updateLead]);

  const handleSaveNotes = useCallback(async () => {
    if (!lead) return;
    setIsSaving(true);
    try {
      await updateLead(lead.id, {
        follow_up_notes: followUpNotes,
        contact_notes: contactNotes,
      });
      Alert.alert('Saved', 'Notes updated successfully');
    } catch {
      Alert.alert('Error', 'Failed to save notes');
    } finally {
      setIsSaving(false);
    }
  }, [lead, followUpNotes, contactNotes, updateLead]);

  const handleCall = useCallback(() => {
    // No phone stored directly, but could be in interactions metadata
    Alert.alert('Contact', 'Phone number not available for this lead.');
  }, []);

  const handleEmail = useCallback(() => {
    if (lead?.user_email) {
      Linking.openURL(`mailto:${lead.user_email}`);
    }
  }, [lead]);

  if (!lead) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}>
          <Text style={styles.errorText}>Lead not found</Text>
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={handleToggleStar}>
            <Text style={styles.starIcon}>{lead.is_starred ? '\u2605' : '\u2606'}</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.content}>
          {/* Lead info */}
          <Text style={styles.leadName}>{lead.user_name || 'Unknown'}</Text>
          {lead.user_title && <Text style={styles.leadTitle}>{lead.user_title}</Text>}
          {lead.user_company && <Text style={styles.leadCompany}>{lead.user_company}</Text>}

          <View style={styles.badgeRow}>
            <Badge
              variant={
                lead.intent_level === 'hot'
                  ? 'destructive'
                  : lead.intent_level === 'warm'
                    ? 'warning'
                    : 'info'
              }
              label={`${lead.intent_level.toUpperCase()} - Score ${lead.intent_score}`}
            />
          </View>

          {/* Quick actions */}
          <View style={styles.actionRow}>
            {lead.user_email && (
              <Button title="Email" onPress={handleEmail} variant="outline" size="sm" style={{ flex: 1 }} />
            )}
            <Button title="Call" onPress={handleCall} variant="outline" size="sm" style={{ flex: 1 }} />
          </View>

          {/* Contact info */}
          <Card style={styles.infoCard}>
            <Text style={styles.sectionTitle}>Contact Information</Text>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Email</Text>
              <Text style={styles.infoValue}>{lead.user_email || 'N/A'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>First Interaction</Text>
              <Text style={styles.infoValue}>
                {new Date(lead.first_interaction_at).toLocaleDateString()}
              </Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Last Interaction</Text>
              <Text style={styles.infoValue}>
                {new Date(lead.last_interaction_at).toLocaleDateString()}
              </Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Interactions</Text>
              <Text style={styles.infoValue}>{lead.interaction_count}</Text>
            </View>
          </Card>

          {/* Follow-up status */}
          <Text style={styles.sectionTitle}>Follow-up Status</Text>
          <View style={styles.statusGrid}>
            {FOLLOW_UP_STATUSES.map((status) => (
              <TouchableOpacity
                key={status.value}
                style={[
                  styles.statusChip,
                  lead.follow_up_status === status.value && {
                    backgroundColor: status.color,
                    borderColor: status.color,
                  },
                ]}
                onPress={() => handleStatusChange(status.value)}
              >
                <Text
                  style={[
                    styles.statusChipText,
                    lead.follow_up_status === status.value && { color: '#fff' },
                  ]}
                >
                  {status.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Notes */}
          <Text style={styles.sectionTitle}>Notes</Text>
          <Input
            label="Follow-up Notes"
            value={followUpNotes}
            onChangeText={setFollowUpNotes}
            placeholder="Add follow-up notes..."
            multiline
            numberOfLines={3}
            style={{ height: 80, textAlignVertical: 'top' }}
          />
          <Input
            label="Contact Notes"
            value={contactNotes}
            onChangeText={setContactNotes}
            placeholder="Additional contact notes..."
            multiline
            numberOfLines={3}
            style={{ height: 80, textAlignVertical: 'top' }}
          />
          <Button
            title="Save Notes"
            onPress={handleSaveNotes}
            loading={isSaving}
            fullWidth
          />

          {/* Interaction history */}
          {lead.interactions.length > 0 && (
            <>
              <Text style={[styles.sectionTitle, { marginTop: 24 }]}>Interaction History</Text>
              {lead.interactions.map((interaction, idx) => (
                <Card key={`${interaction.type}-${idx}`} style={styles.interactionCard}>
                  <View style={styles.interactionRow}>
                    <Text style={styles.interactionType}>{interaction.type.replace(/_/g, ' ')}</Text>
                    <Text style={styles.interactionTime}>
                      {new Date(interaction.timestamp).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      })}
                    </Text>
                  </View>
                </Card>
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  errorText: { ...typography.h3, color: colors.foreground, marginBottom: 16 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backText: { ...typography.label, color: colors.primary.gold },
  starIcon: { fontSize: 24, color: colors.primary.gold },
  content: { padding: 20 },
  leadName: { ...typography.h2, color: colors.foreground },
  leadTitle: { ...typography.body, color: colors.neutral[500], marginTop: 4 },
  leadCompany: { ...typography.body, color: colors.neutral[600], fontWeight: '500' },
  badgeRow: { flexDirection: 'row', marginTop: 8, gap: 8 },
  actionRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  infoCard: { padding: 16, marginTop: 20 },
  sectionTitle: { ...typography.h4, color: colors.foreground, marginTop: 20, marginBottom: 10 },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  infoLabel: { ...typography.bodySmall, color: colors.neutral[500] },
  infoValue: { ...typography.bodySmall, color: colors.foreground, fontWeight: '500' },
  statusGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  statusChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  statusChipText: { ...typography.bodySmall, color: colors.neutral[600], fontWeight: '500' },
  interactionCard: { padding: 12, marginBottom: 8 },
  interactionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  interactionType: { ...typography.body, color: colors.foreground, fontWeight: '500', textTransform: 'capitalize' },
  interactionTime: { ...typography.caption, color: colors.neutral[400] },
});
