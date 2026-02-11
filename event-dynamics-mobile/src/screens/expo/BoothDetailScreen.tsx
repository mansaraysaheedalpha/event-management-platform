import React, { useEffect, useCallback } from 'react';
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
import { Image } from 'expo-image';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useExpo } from '@/hooks/useExpo';
import { Card, Badge, Button, Avatar, SessionDetailSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';
import { BOOTH_TIER_COLORS } from '@/types/expo';
import type { BoothResource, BoothStaffPresence } from '@/types/expo';

type Nav = NativeStackNavigationProp<HomeStackParamList, 'BoothDetail'>;
type Route = RouteProp<HomeStackParamList, 'BoothDetail'>;

const RESOURCE_ICON_MAP: Record<string, string> = {
  PDF: 'PDF',
  VIDEO: 'VID',
  IMAGE: 'IMG',
  DOCUMENT: 'DOC',
  LINK: 'LNK',
  OTHER: 'FILE',
};

const STAFF_STATUS_COLORS: Record<string, string> = {
  ONLINE: colors.success,
  AWAY: colors.warning,
  BUSY: colors.destructive,
  OFFLINE: colors.neutral[400],
};

const ResourceItem = React.memo(function ResourceItem({
  resource,
  onPress,
}: {
  resource: BoothResource;
  onPress: () => void;
}) {

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
      <Card style={styles.resourceCard}>
        <View style={styles.resourceIcon}>
          <Text style={styles.resourceIconText}>{RESOURCE_ICON_MAP[resource.type] || 'FILE'}</Text>
        </View>
        <View style={styles.resourceInfo}>
          <Text style={styles.resourceName} numberOfLines={1}>
            {resource.name}
          </Text>
          {resource.description && (
            <Text style={styles.resourceDesc} numberOfLines={1}>
              {resource.description}
            </Text>
          )}
          <Text style={styles.resourceMeta}>
            {resource.downloadCount} downloads
          </Text>
        </View>
      </Card>
    </TouchableOpacity>
  );
});

const StaffMember = React.memo(function StaffMember({ staff }: { staff: BoothStaffPresence }) {
  return (
    <View style={styles.staffItem}>
      <Avatar uri={staff.staffAvatarUrl} name={staff.staffName} size={36} />
      <View style={styles.staffInfo}>
        <Text style={styles.staffName}>{staff.staffName}</Text>
        <View style={styles.staffStatus}>
          <View
            style={[
              styles.staffDot,
              { backgroundColor: STAFF_STATUS_COLORS[staff.status] || colors.neutral[400] },
            ]}
          />
          <Text style={styles.staffStatusText}>{staff.status.toLowerCase()}</Text>
        </View>
      </View>
    </View>
  );
});

export function BoothDetailScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { eventId, boothId } = route.params;

  const {
    currentBooth: booth,
    isLoading,
    error,
    enterBooth,
    leaveBooth,
    trackResourceDownload,
  } = useExpo({ eventId });

  useEffect(() => {
    enterBooth(boothId);
    return () => {
      leaveBooth();
    };
  }, [boothId, enterBooth, leaveBooth]);

  const handleResourcePress = useCallback(
    async (resource: BoothResource) => {
      trackResourceDownload(boothId, resource.id);
      if (resource.url) {
        const canOpen = await Linking.canOpenURL(resource.url);
        if (canOpen) {
          Linking.openURL(resource.url);
        } else {
          Alert.alert('Cannot Open', 'Unable to open this resource.');
        }
      }
    },
    [boothId, trackResourceDownload],
  );

  const handleCtaPress = useCallback(async (url: string) => {
    const canOpen = await Linking.canOpenURL(url);
    if (canOpen) {
      Linking.openURL(url);
    }
  }, []);

  if (isLoading && !booth) {
    return <SessionDetailSkeleton />;
  }

  if (!booth) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}>
          <Text style={styles.errorTitle}>Booth not found</Text>
          {error && <Text style={styles.errorMsg}>{error}</Text>}
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

  const tierStyle = BOOTH_TIER_COLORS[booth.tier];
  const onlineStaff = booth.staffPresence.filter((s) => s.status === 'ONLINE');

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Banner */}
        {booth.bannerUrl ? (
          <Image
            source={{ uri: booth.bannerUrl }}
            style={styles.banner}
            contentFit="cover"
            placeholder={{ blurhash: imageConfig.defaultBlurhash }}
            cachePolicy={imageConfig.cachePolicy}
            transition={imageConfig.transition}
          />
        ) : (
          <View style={[styles.banner, { backgroundColor: tierStyle.bg }]}>
            {booth.logoUrl ? (
              <Image
                source={{ uri: booth.logoUrl }}
                style={styles.centerLogo}
                contentFit="contain"
                placeholder={{ blurhash: imageConfig.defaultBlurhash }}
                cachePolicy={imageConfig.cachePolicy}
                transition={imageConfig.transition}
              />
            ) : (
              <Text style={[styles.bannerInitial, { color: tierStyle.color }]}>
                {booth.name.charAt(0)}
              </Text>
            )}
          </View>
        )}

        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Text style={styles.backBtnText}>Back</Text>
        </TouchableOpacity>

        <View style={styles.content}>
          {/* Name & tier */}
          <View style={styles.titleRow}>
            <Text style={styles.boothName}>{booth.name}</Text>
            <View style={[styles.tierBadge, { backgroundColor: tierStyle.bg }]}>
              <Text style={[styles.tierText, { color: tierStyle.color }]}>{booth.tier}</Text>
            </View>
          </View>

          {booth.tagline && <Text style={styles.tagline}>{booth.tagline}</Text>}

          {/* Stats */}
          <View style={styles.statsRow}>
            <Card style={styles.statCard}>
              <Text style={styles.statNumber}>{booth._count.visits}</Text>
              <Text style={styles.statLabel}>Visitors</Text>
            </Card>
            <Card style={styles.statCard}>
              <Text style={styles.statNumber}>{booth.resources.length}</Text>
              <Text style={styles.statLabel}>Resources</Text>
            </Card>
            <Card style={styles.statCard}>
              <Text style={styles.statNumber}>{onlineStaff.length}</Text>
              <Text style={styles.statLabel}>Staff Online</Text>
            </Card>
          </View>

          {/* CTA Buttons */}
          {booth.ctaButtons.length > 0 && (
            <View style={styles.ctaRow}>
              {booth.ctaButtons
                .sort((a, b) => a.order - b.order)
                .map((cta) => (
                  <Button
                    key={cta.id}
                    title={cta.label}
                    onPress={() => handleCtaPress(cta.url)}
                    variant={cta.style === 'primary' ? 'primary' : cta.style === 'secondary' ? 'secondary' : 'outline'}
                    size="sm"
                    style={{ flex: 1 }}
                  />
                ))}
            </View>
          )}

          {/* Chat button — booth chat is accessed via SponsorMessages or as a modal */}
          {booth.chatEnabled && (
            <Button
              title="Chat with Booth Staff"
              onPress={() =>
                Alert.alert('Booth Chat', 'Use the Expo Hall chat to message booth staff.')
              }
              variant="primary"
              fullWidth
              style={{ marginTop: 12 }}
            />
          )}

          {/* Description */}
          {booth.description && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>About</Text>
              <Text style={styles.description}>{booth.description}</Text>
            </View>
          )}

          {/* Resources */}
          {booth.resources.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Resources</Text>
              {booth.resources.map((resource) => (
                <ResourceItem
                  key={resource.id}
                  resource={resource}
                  onPress={() => handleResourcePress(resource)}
                />
              ))}
            </View>
          )}

          {/* Staff */}
          {booth.staffPresence.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Team</Text>
              {booth.staffPresence.map((staff) => (
                <StaffMember key={staff.staffId} staff={staff} />
              ))}
            </View>
          )}

          {/* Booth number */}
          {booth.boothNumber && (
            <View style={styles.section}>
              <Text style={styles.boothNumber}>Booth #{booth.boothNumber}</Text>
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  errorTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  errorMsg: { ...typography.body, color: colors.neutral[500], marginBottom: 16 },
  banner: { width: '100%', height: 180, justifyContent: 'center', alignItems: 'center' },
  centerLogo: { width: 100, height: 100 },
  bannerInitial: { fontSize: 64, fontWeight: '800' },
  backBtn: {
    position: 'absolute',
    top: 12,
    left: 16,
    backgroundColor: 'rgba(0,0,0,0.5)',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
  },
  backBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  content: { padding: 20 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  boothName: { ...typography.h2, color: colors.foreground, flex: 1 },
  tierBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6 },
  tierText: { ...typography.caption, fontWeight: '700' },
  tagline: { ...typography.body, color: colors.neutral[500], marginTop: 4 },
  statsRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  statCard: { flex: 1, padding: 12, alignItems: 'center' },
  statNumber: { ...typography.h3, color: colors.primary.gold },
  statLabel: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  ctaRow: { flexDirection: 'row', gap: 8, marginTop: 16 },
  section: { marginTop: 24 },
  sectionTitle: {
    ...typography.h4,
    color: colors.foreground,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 10,
  },
  description: { ...typography.body, color: colors.neutral[600], lineHeight: 24 },
  resourceCard: {
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 8,
  },
  resourceIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: colors.neutral[100],
    justifyContent: 'center',
    alignItems: 'center',
  },
  resourceIconText: { ...typography.caption, color: colors.neutral[600], fontWeight: '700' },
  resourceInfo: { flex: 1 },
  resourceName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  resourceDesc: { ...typography.bodySmall, color: colors.neutral[500] },
  resourceMeta: { ...typography.caption, color: colors.neutral[400], marginTop: 2 },
  staffItem: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  staffInfo: { flex: 1 },
  staffName: { ...typography.body, color: colors.foreground, fontWeight: '500' },
  staffStatus: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  staffDot: { width: 6, height: 6, borderRadius: 3 },
  staffStatusText: { ...typography.caption, color: colors.neutral[500], textTransform: 'capitalize' },
  boothNumber: { ...typography.bodySmall, color: colors.neutral[400], textAlign: 'center' },
});
