import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { Image } from 'expo-image';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { GET_PUBLIC_EVENTS_QUERY } from '@/graphql/public.graphql';
import { Card, Badge, ScreenSkeleton, EventBrowseCardSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { ExploreStackParamList } from '@/navigation/types';

type ExploreNav = NativeStackNavigationProp<ExploreStackParamList, 'EventBrowse'>;

interface EventVenue {
  id: string;
  name: string;
}

interface PublicEvent {
  id: string;
  name: string;
  description?: string;
  startDate: string;
  endDate: string;
  imageUrl?: string;
  isSoldOut: boolean;
  venue?: EventVenue;
}

interface PublicEventsResponse {
  publicEvents: {
    totalCount: number;
    events: PublicEvent[];
  };
}

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const CARD_IMAGE_HEIGHT = (SCREEN_WIDTH - 48) * 0.56; // ~16:9

function formatDateRange(startDate: string, endDate: string): string {
  const start = new Date(startDate);
  const end = new Date(endDate);
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  const startStr = start.toLocaleDateString('en-US', { ...opts, weekday: 'short' });

  if (start.toDateString() === end.toDateString()) {
    return startStr;
  }
  const endStr = end.toLocaleDateString('en-US', opts);
  return `${startStr} - ${endStr}`;
}

function EventCard({ event, onPress }: { event: PublicEvent; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8} accessibilityRole="button" accessibilityLabel={`Navigate to ${event.name}`}>
      <Card style={styles.card}>
        {event.imageUrl ? (
          <Image
            source={{ uri: event.imageUrl }}
            style={styles.cardImage}
            contentFit="cover"
            transition={imageConfig.transition}
            placeholder={{ blurhash: imageConfig.defaultBlurhash }}
            cachePolicy={imageConfig.cachePolicy}
            accessibilityLabel={`${event.name} event image`}
          />
        ) : (
          <View style={[styles.cardImage, styles.placeholderImage]}>
            <Text style={styles.placeholderText}>ED</Text>
          </View>
        )}

        <View style={styles.dateBadge}>
          <Text style={styles.dateBadgeText}>
            {formatDateRange(event.startDate, event.endDate)}
          </Text>
        </View>

        {event.isSoldOut && (
          <View style={styles.soldOutBadge}>
            <Badge variant="destructive" label="Sold Out" />
          </View>
        )}

        <View style={styles.cardBody}>
          <Text style={styles.cardTitle} numberOfLines={2}>
            {event.name}
          </Text>
          {event.description ? (
            <Text style={styles.cardDesc} numberOfLines={2}>
              {event.description}
            </Text>
          ) : null}
          {event.venue?.name ? (
            <Text style={styles.cardVenue} numberOfLines={1}>
              {event.venue.name}
            </Text>
          ) : null}
        </View>
      </Card>
    </TouchableOpacity>
  );
}

export function EventBrowseScreen() {
  const navigation = useNavigation<ExploreNav>();

  const { data, loading, error, refetch } = useQuery<PublicEventsResponse>(
    GET_PUBLIC_EVENTS_QUERY,
    {
      variables: { limit: 20, offset: 0, includePast: false },
      fetchPolicy: 'cache-and-network',
    },
  );

  const events = data?.publicEvents?.events ?? [];
  const totalCount = data?.publicEvents?.totalCount ?? 0;

  const handleEventPress = useCallback(
    (eventId: string) => {
      navigation.navigate('PublicEventDetail', { eventId });
    },
    [navigation],
  );

  const renderEvent = useCallback(
    ({ item }: { item: PublicEvent }) => (
      <EventCard event={item} onPress={() => handleEventPress(item.id)} />
    ),
    [handleEventPress],
  );

  if (loading && !data) {
    return <ScreenSkeleton count={3} ItemSkeleton={EventBrowseCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">Explore Events</Text>
        <Text style={styles.subtitle}>
          {totalCount > 0
            ? `${totalCount} upcoming event${totalCount !== 1 ? 's' : ''}`
            : 'Discover exciting events near you'}
        </Text>
      </View>

      {error && !data ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>Something went wrong</Text>
          <Text style={styles.emptyText}>Failed to load events. Please try again later.</Text>
        </View>
      ) : events.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>No upcoming events</Text>
          <Text style={styles.emptyText}>
            Check back later for new events.
          </Text>
        </View>
      ) : (
        <FlashList
          data={events}
          renderItem={renderEvent}
          keyExtractor={(item) => item.id}
          estimatedItemSize={280}
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
  card: { marginBottom: 16, overflow: 'hidden', padding: 0 },
  cardImage: { width: '100%', height: CARD_IMAGE_HEIGHT, borderTopLeftRadius: 12, borderTopRightRadius: 12 },
  placeholderImage: {
    backgroundColor: colors.primary.navy,
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholderText: { fontSize: 32, fontWeight: '800', color: colors.primary.gold },
  dateBadge: {
    position: 'absolute',
    top: 12,
    left: 12,
    backgroundColor: 'rgba(255,255,255,0.95)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  dateBadgeText: { ...typography.caption, color: colors.foreground, fontWeight: '700' },
  soldOutBadge: { position: 'absolute', top: 12, right: 12 },
  cardBody: { padding: 16 },
  cardTitle: { ...typography.h4, color: colors.foreground, marginBottom: 4 },
  cardDesc: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 8 },
  cardVenue: { ...typography.caption, color: colors.neutral[400] },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
