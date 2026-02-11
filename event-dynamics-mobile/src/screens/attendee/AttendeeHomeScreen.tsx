import React, { useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { Image } from 'expo-image';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { GET_MY_REGISTRATIONS_QUERY } from '@/graphql/attendee.graphql';
import { Card, Badge, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type HomeNav = NativeStackNavigationProp<HomeStackParamList, 'AttendeeHome'>;

interface EventVenue {
  id: string;
  name: string;
  address?: string;
}

interface RegistrationEvent {
  id: string;
  name: string;
  description?: string;
  startDate: string;
  endDate: string;
  status: string;
  imageUrl?: string;
  venue?: EventVenue;
}

interface Registration {
  id: string;
  status: string;
  ticketCode: string;
  checkedInAt?: string;
  event: RegistrationEvent;
}

interface MyRegistrationsResponse {
  myRegistrations: Registration[];
}

function getEventStatus(event: RegistrationEvent): 'live' | 'upcoming' | 'ended' {
  const now = new Date();
  const start = new Date(event.startDate);
  const end = new Date(event.endDate);
  if (now >= start && now <= end) return 'live';
  if (now < start) return 'upcoming';
  return 'ended';
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function RegistrationCard({
  registration,
  onPress,
}: {
  registration: Registration;
  onPress: () => void;
}) {
  const eventStatus = getEventStatus(registration.event);
  const isLive = eventStatus === 'live';

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8} accessibilityRole="button" accessibilityLabel={`Navigate to ${registration.event.name}`}>
      <Card style={isLive ? { ...styles.regCard, borderColor: colors.success, borderWidth: 2 } : styles.regCard}>
        <View style={styles.regRow}>
          {registration.event.imageUrl ? (
            <Image
              source={{ uri: registration.event.imageUrl }}
              style={styles.regImage}
              contentFit="cover"
              placeholder={{ blurhash: imageConfig.defaultBlurhash }}
              cachePolicy={imageConfig.cachePolicy}
              transition={imageConfig.transition}
              accessibilityLabel={`${registration.event.name} event image`}
            />
          ) : (
            <View style={[styles.regImage, styles.regImagePlaceholder]}>
              <Text style={styles.regImageText}>ED</Text>
            </View>
          )}

          <View style={styles.regInfo}>
            <View style={styles.regBadgeRow}>
              {isLive && <Badge variant="success" label="Live Now" />}
              {eventStatus === 'upcoming' && <Badge variant="info" label="Upcoming" />}
              {eventStatus === 'ended' && <Badge variant="default" label="Ended" />}
              {registration.checkedInAt && <Badge variant="success" label="Checked In" />}
            </View>

            <Text style={styles.regTitle} numberOfLines={2}>
              {registration.event.name}
            </Text>

            <Text style={styles.regDate}>
              {formatDate(registration.event.startDate)} at{' '}
              {formatTime(registration.event.startDate)}
            </Text>

            {registration.event.venue?.name && (
              <Text style={styles.regVenue} numberOfLines={1}>
                {registration.event.venue.name}
              </Text>
            )}

            <Text style={styles.regTicket}>
              Ticket: {registration.ticketCode}
            </Text>
          </View>
        </View>
      </Card>
    </TouchableOpacity>
  );
}

export function AttendeeHomeScreen() {
  const navigation = useNavigation<HomeNav>();

  const { data, loading, refetch } = useQuery<MyRegistrationsResponse>(
    GET_MY_REGISTRATIONS_QUERY,
    { fetchPolicy: 'cache-and-network' },
  );

  const { upcoming, past } = useMemo(() => {
    const regs = data?.myRegistrations ?? [];
    const upcomingList: Registration[] = [];
    const pastList: Registration[] = [];

    for (const reg of regs) {
      const status = getEventStatus(reg.event);
      if (status === 'ended') {
        pastList.push(reg);
      } else {
        upcomingList.push(reg);
      }
    }

    // Sort: live first, then by date ascending
    upcomingList.sort((a, b) => {
      const aLive = getEventStatus(a.event) === 'live' ? 0 : 1;
      const bLive = getEventStatus(b.event) === 'live' ? 0 : 1;
      if (aLive !== bLive) return aLive - bLive;
      return new Date(a.event.startDate).getTime() - new Date(b.event.startDate).getTime();
    });

    pastList.sort(
      (a, b) => new Date(b.event.startDate).getTime() - new Date(a.event.startDate).getTime(),
    );

    return { upcoming: upcomingList, past: pastList };
  }, [data]);

  const allSections = useMemo(() => {
    const items: (Registration | { type: 'header'; title: string })[] = [];
    if (upcoming.length > 0) {
      items.push({ type: 'header', title: 'Upcoming & Live Events' });
      items.push(...upcoming);
    }
    if (past.length > 0) {
      items.push({ type: 'header', title: 'Past Events' });
      items.push(...past);
    }
    return items;
  }, [upcoming, past]);

  const handleEventPress = useCallback(
    (eventId: string) => {
      navigation.navigate('EventHub', { eventId });
    },
    [navigation],
  );

  const renderItem = useCallback(
    ({ item }: { item: Registration | { type: 'header'; title: string } }) => {
      if ('type' in item && item.type === 'header') {
        return <Text style={styles.sectionHeader}>{item.title}</Text>;
      }
      const reg = item as Registration;
      return <RegistrationCard registration={reg} onPress={() => handleEventPress(reg.event.id)} />;
    },
    [handleEventPress],
  );

  if (loading && !data) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">My Events</Text>
        <Text style={styles.subtitle}>Your registered events</Text>
      </View>

      {allSections.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>No events yet</Text>
          <Text style={styles.emptyText}>
            Browse and register for events to see them here.
          </Text>
        </View>
      ) : (
        <FlashList
          data={allSections}
          renderItem={renderItem}
          keyExtractor={(item, index) =>
            'type' in item ? `header-${index}` : item.id
          }
          estimatedItemSize={100}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={refetch}
              tintColor={colors.primary.gold}
            />
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 12 },
  title: { ...typography.h1, color: colors.foreground, marginBottom: 4 },
  subtitle: { ...typography.body, color: colors.neutral[500] },
  list: { paddingHorizontal: 24, paddingBottom: 24 },
  sectionHeader: { ...typography.h3, color: colors.foreground, marginTop: 16, marginBottom: 12 },
  regCard: { marginBottom: 12, padding: 12 },
  regRow: { flexDirection: 'row', gap: 12 },
  regImage: { width: 80, height: 80, borderRadius: 8 },
  regImagePlaceholder: { backgroundColor: colors.primary.navy, justifyContent: 'center', alignItems: 'center' },
  regImageText: { fontSize: 16, fontWeight: '800', color: colors.primary.gold },
  regInfo: { flex: 1 },
  regBadgeRow: { flexDirection: 'row', gap: 6, marginBottom: 4, flexWrap: 'wrap' },
  regTitle: { ...typography.body, color: colors.foreground, fontWeight: '700', marginBottom: 2 },
  regDate: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 2 },
  regVenue: { ...typography.caption, color: colors.neutral[400], marginBottom: 2 },
  regTicket: { ...typography.caption, color: colors.primary.gold, fontWeight: '600' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
