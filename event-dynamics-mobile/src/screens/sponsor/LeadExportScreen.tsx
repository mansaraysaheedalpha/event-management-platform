import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Alert,
  Share,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { TouchableOpacity } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useLeads } from '@/hooks/useLeads';
import { Card, Button, Badge } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'LeadExport'>;
type Route = RouteProp<SponsorStackParamList, 'LeadExport'>;

export function LeadExportScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId } = route.params;

  const { leads, stats } = useLeads({ sponsorId });
  const [isExporting, setIsExporting] = useState(false);

  const generateCSV = useCallback(() => {
    const headers = [
      'Name',
      'Email',
      'Company',
      'Title',
      'Intent Level',
      'Intent Score',
      'Follow-up Status',
      'First Interaction',
      'Last Interaction',
      'Interaction Count',
      'Starred',
    ];

    const rows = leads.map((lead) => [
      lead.user_name || '',
      lead.user_email || '',
      lead.user_company || '',
      lead.user_title || '',
      lead.intent_level,
      String(lead.intent_score),
      lead.follow_up_status,
      lead.first_interaction_at,
      lead.last_interaction_at,
      String(lead.interaction_count),
      lead.is_starred ? 'Yes' : 'No',
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row) =>
        row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(','),
      ),
    ].join('\n');

    return csvContent;
  }, [leads]);

  const handleExportCSV = useCallback(async () => {
    setIsExporting(true);
    try {
      const csv = generateCSV();
      await Share.share({
        message: csv,
        title: `Leads Export - ${new Date().toLocaleDateString()}`,
      });
    } catch (err) {
      if ((err as Error).message !== 'User did not share') {
        Alert.alert('Error', 'Failed to export leads');
      }
    } finally {
      setIsExporting(false);
    }
  }, [generateCSV]);

  const handleExportSummary = useCallback(async () => {
    if (!stats) return;

    const summary = [
      `Lead Summary Report`,
      `Generated: ${new Date().toLocaleString()}`,
      ``,
      `Total Leads: ${stats.total_leads}`,
      `Hot Leads: ${stats.hot_leads}`,
      `Warm Leads: ${stats.warm_leads}`,
      `Cold Leads: ${stats.cold_leads}`,
      `Contacted: ${stats.leads_contacted}`,
      `Converted: ${stats.leads_converted}`,
      `Conversion Rate: ${(stats.conversion_rate * 100).toFixed(1)}%`,
      `Average Intent Score: ${stats.avg_intent_score.toFixed(1)}`,
    ].join('\n');

    try {
      await Share.share({
        message: summary,
        title: 'Lead Summary Report',
      });
    } catch {
      // User cancelled
    }
  }, [stats]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Export</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.content}>
        {/* Summary */}
        <Card style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Export Summary</Text>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Total leads to export</Text>
            <Text style={styles.summaryValue}>{leads.length}</Text>
          </View>
          {stats && (
            <>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Hot / Warm / Cold</Text>
                <Text style={styles.summaryValue}>
                  {stats.hot_leads} / {stats.warm_leads} / {stats.cold_leads}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Conversion Rate</Text>
                <Text style={styles.summaryValue}>
                  {(stats.conversion_rate * 100).toFixed(1)}%
                </Text>
              </View>
            </>
          )}
        </Card>

        {/* Export options */}
        <Text style={styles.sectionTitle}>Export Options</Text>

        <TouchableOpacity onPress={handleExportCSV} disabled={isExporting}>
          <Card style={styles.exportCard}>
            <View>
              <Text style={styles.exportTitle}>Export as CSV</Text>
              <Text style={styles.exportDesc}>
                Share full lead data as CSV via email, messages, or other apps
              </Text>
            </View>
            <Badge variant="info" label="CSV" />
          </Card>
        </TouchableOpacity>

        <TouchableOpacity onPress={handleExportSummary}>
          <Card style={styles.exportCard}>
            <View>
              <Text style={styles.exportTitle}>Share Summary</Text>
              <Text style={styles.exportDesc}>
                Share a quick summary of lead statistics
              </Text>
            </View>
            <Badge variant="default" label="Text" />
          </Card>
        </TouchableOpacity>

        <Button
          title={isExporting ? 'Exporting...' : 'Export All Leads (CSV)'}
          onPress={handleExportCSV}
          loading={isExporting}
          fullWidth
          style={{ marginTop: 24 }}
        />
      </View>
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
  content: { padding: 20 },
  summaryCard: { padding: 16 },
  summaryTitle: { ...typography.h4, color: colors.foreground, marginBottom: 12 },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  summaryLabel: { ...typography.bodySmall, color: colors.neutral[500] },
  summaryValue: { ...typography.bodySmall, color: colors.foreground, fontWeight: '600' },
  sectionTitle: { ...typography.h4, color: colors.foreground, marginTop: 24, marginBottom: 12 },
  exportCard: {
    padding: 16,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  exportTitle: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  exportDesc: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
});
