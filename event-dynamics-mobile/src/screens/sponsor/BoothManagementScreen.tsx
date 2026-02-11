import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';
import { Card, Button, Badge, Avatar, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';
import type { Sponsor, SponsorUser } from '@/types/sponsor';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'BoothManagement'>;
type Route = RouteProp<SponsorStackParamList, 'BoothManagement'>;

// Simple camelCase converter for API responses
function toCamelCase<T>(obj: Record<string, unknown>): T {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    result[camelKey] = value;
  }
  return result as T;
}

export function BoothManagementScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId } = route.params;

  const { token, orgId } = useAuthStore();
  const [sponsor, setSponsor] = useState<Sponsor | null>(null);
  const [team, setTeam] = useState<SponsorUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSponsor = useCallback(async () => {
    if (!token || !orgId) return;

    try {
      const response = await fetch(
        `${env.EVENT_SERVICE_URL}/sponsors/organizations/${orgId}/sponsors/${sponsorId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        },
      );
      if (response.ok) {
        const data = await response.json();
        setSponsor(toCamelCase<Sponsor>(data));
      }
    } catch (err) {
      console.error('Failed to fetch sponsor:', err);
    }
  }, [token, orgId, sponsorId]);

  const fetchTeam = useCallback(async () => {
    if (!token || !orgId) return;

    try {
      const response = await fetch(
        `${env.EVENT_SERVICE_URL}/sponsors/organizations/${orgId}/sponsors/${sponsorId}/users`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        },
      );
      if (response.ok) {
        const data = await response.json();
        setTeam(data);
      }
    } catch (err) {
      console.error('Failed to fetch team:', err);
    }
  }, [token, orgId, sponsorId]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([fetchSponsor(), fetchTeam()]);
    setIsLoading(false);
  }, [fetchSponsor, fetchTeam]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  if (isLoading) {
    return <ScreenSkeleton count={3} ItemSkeleton={EventCardSkeleton} />;
  }

  if (!sponsor) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}>
          <Text style={styles.errorText}>Sponsor not found</Text>
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Booth Settings</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary.gold} />
        }
      >
        {/* Company info */}
        <Card style={styles.companyCard}>
          {sponsor.companyLogoUrl && (
            <Image
              source={{ uri: sponsor.companyLogoUrl }}
              style={styles.companyLogo}
              contentFit="contain"
              placeholder={{ blurhash: imageConfig.defaultBlurhash }}
              cachePolicy={imageConfig.cachePolicy}
              transition={imageConfig.transition}
            />
          )}
          <Text style={styles.companyName}>{sponsor.companyName}</Text>
          {sponsor.tier && (
            <Badge variant="info" label={sponsor.tier.name} />
          )}
          {sponsor.companyDescription && (
            <Text style={styles.companyDesc}>{sponsor.companyDescription}</Text>
          )}
        </Card>

        {/* Booth info */}
        <Text style={styles.sectionTitle}>Booth Details</Text>
        <Card style={styles.detailCard}>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Booth Number</Text>
            <Text style={styles.detailValue}>{sponsor.boothNumber || 'N/A'}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Lead Capture</Text>
            <Badge
              variant={sponsor.leadCaptureEnabled ? 'success' : 'default'}
              label={sponsor.leadCaptureEnabled ? 'Enabled' : 'Disabled'}
            />
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Active</Text>
            <Badge
              variant={sponsor.isActive ? 'success' : 'default'}
              label={sponsor.isActive ? 'Yes' : 'No'}
            />
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Featured</Text>
            <Badge
              variant={sponsor.isFeatured ? 'warning' : 'default'}
              label={sponsor.isFeatured ? 'Yes' : 'No'}
            />
          </View>
        </Card>

        {/* Contact info */}
        <Text style={styles.sectionTitle}>Contact</Text>
        <Card style={styles.detailCard}>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Name</Text>
            <Text style={styles.detailValue}>{sponsor.contactName || 'N/A'}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Email</Text>
            <Text style={styles.detailValue}>{sponsor.contactEmail || 'N/A'}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Phone</Text>
            <Text style={styles.detailValue}>{sponsor.contactPhone || 'N/A'}</Text>
          </View>
          {sponsor.companyWebsite && (
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Website</Text>
              <Text style={[styles.detailValue, { color: colors.primary.gold }]} numberOfLines={1}>
                {sponsor.companyWebsite}
              </Text>
            </View>
          )}
        </Card>

        {/* Marketing assets */}
        {sponsor.marketingAssets.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Marketing Assets</Text>
            {sponsor.marketingAssets.map((asset, idx) => (
              <Card key={idx} style={styles.assetCard}>
                <Text style={styles.assetName}>{asset.name}</Text>
                <Text style={styles.assetType}>{asset.type}</Text>
              </Card>
            ))}
          </>
        )}

        {/* Team */}
        <Text style={styles.sectionTitle}>Team ({team.length})</Text>
        {team.map((member) => (
          <Card key={member.id} style={styles.teamCard}>
            <View style={styles.teamRow}>
              <View style={styles.teamInfo}>
                <Text style={styles.teamRole}>{member.role}</Text>
                <View style={styles.permissionRow}>
                  {member.canViewLeads && <Badge variant="default" label="Leads" />}
                  {member.canManageBooth && <Badge variant="default" label="Manage" />}
                  {member.canMessageAttendees && <Badge variant="default" label="Message" />}
                </View>
              </View>
              <Badge
                variant={member.isActive ? 'success' : 'default'}
                label={member.isActive ? 'Active' : 'Inactive'}
              />
            </View>
          </Card>
        ))}
        {team.length === 0 && (
          <Text style={styles.emptyText}>No team members assigned yet</Text>
        )}
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
  companyCard: { padding: 20, alignItems: 'center', gap: 8 },
  companyLogo: { width: 80, height: 80, borderRadius: 12 },
  companyName: { ...typography.h2, color: colors.foreground },
  companyDesc: { ...typography.body, color: colors.neutral[500], textAlign: 'center', marginTop: 4 },
  sectionTitle: {
    ...typography.h4,
    color: colors.foreground,
    marginTop: 24,
    marginBottom: 10,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 10,
  },
  detailCard: { padding: 14 },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  detailLabel: { ...typography.bodySmall, color: colors.neutral[500] },
  detailValue: { ...typography.bodySmall, color: colors.foreground, fontWeight: '500' },
  assetCard: { padding: 12, marginBottom: 8, flexDirection: 'row', justifyContent: 'space-between' },
  assetName: { ...typography.body, color: colors.foreground, fontWeight: '500' },
  assetType: { ...typography.caption, color: colors.neutral[400] },
  teamCard: { padding: 12, marginBottom: 8 },
  teamRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  teamInfo: { flex: 1 },
  teamRole: { ...typography.body, color: colors.foreground, fontWeight: '600', textTransform: 'capitalize' },
  permissionRow: { flexDirection: 'row', gap: 6, marginTop: 4 },
  emptyText: { ...typography.body, color: colors.neutral[400], textAlign: 'center', paddingVertical: 20 },
});
