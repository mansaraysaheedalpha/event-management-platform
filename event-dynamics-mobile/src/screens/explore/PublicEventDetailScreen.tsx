import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { Image } from 'expo-image';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { GET_PUBLIC_EVENT_DETAILS_QUERY } from '@/graphql/public.graphql';
import { GET_EVENT_TICKET_TYPES_QUERY } from '@/graphql/payments.graphql';
import { Card, Badge, Button, SessionDetailSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { ExploreStackParamList } from '@/navigation/types';

type DetailNav = NativeStackNavigationProp<ExploreStackParamList, 'PublicEventDetail'>;
type DetailRoute = RouteProp<ExploreStackParamList, 'PublicEventDetail'>;

interface Session {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  speakers: { id: string; name: string }[];
}

interface EventDetails {
  id: string;
  name: string;
  description?: string;
  startDate: string;
  endDate: string;
  imageUrl?: string;
  maxAttendees?: number;
  registrationsCount: number;
  isSoldOut: boolean;
  availableSpots?: number;
  venue?: { id: string; name: string };
}

interface TicketType {
  id: string;
  name: string;
  price: { amount: number; currency: string; formatted: string };
  isOnSale: boolean;
}

interface EventDetailsResponse {
  event: EventDetails;
  publicSessionsByEvent: Session[];
}

interface TicketTypesResponse {
  eventTicketTypes: TicketType[];
}

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const HERO_HEIGHT = SCREEN_WIDTH * 0.6;

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function getPriceDisplay(tickets: TicketType[]): string {
  const onSale = tickets.filter((t) => t.isOnSale);
  if (onSale.length === 0) return 'Free';
  const prices = onSale.map((t) => t.price.amount);
  const min = Math.min(...prices);
  if (min === 0) return 'Free';
  const max = Math.max(...prices);
  const format = (cents: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
  if (min === max) return format(min);
  return `From ${format(min)}`;
}

export function PublicEventDetailScreen() {
  const navigation = useNavigation<DetailNav>();
  const route = useRoute<DetailRoute>();
  const { eventId } = route.params;

  const { data, loading } = useQuery<EventDetailsResponse>(
    GET_PUBLIC_EVENT_DETAILS_QUERY,
    { variables: { eventId } },
  );

  const { data: ticketData } = useQuery<TicketTypesResponse>(
    GET_EVENT_TICKET_TYPES_QUERY,
    { variables: { eventId } },
  );

  if (loading && !data) {
    return <SessionDetailSkeleton />;
  }

  const event = data?.event;
  const sessions = data?.publicSessionsByEvent ?? [];
  const tickets = ticketData?.eventTicketTypes ?? [];

  if (!event) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <Text style={styles.errorTitle}>Event not found</Text>
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

  const spotsInfo =
    event.isSoldOut
      ? 'Sold Out'
      : event.availableSpots != null && event.availableSpots <= 20
        ? `Only ${event.availableSpots} spots left!`
        : event.maxAttendees
          ? `${event.registrationsCount} / ${event.maxAttendees} registered`
          : `${event.registrationsCount} registered`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Hero */}
        {event.imageUrl ? (
          <Image
            source={{ uri: event.imageUrl }}
            style={styles.hero}
            contentFit="cover"
            placeholder={{ blurhash: imageConfig.defaultBlurhash }}
            cachePolicy={imageConfig.cachePolicy}
            transition={imageConfig.transition}
          />
        ) : (
          <View style={[styles.hero, styles.heroPlaceholder]}>
            <Text style={styles.heroPlaceholderText}>ED</Text>
          </View>
        )}

        {/* Back button overlay */}
        <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>

        <View style={styles.content}>
          {/* Title & Meta */}
          <Text style={styles.eventTitle}>{event.name}</Text>

          <View style={styles.metaRow}>
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>Date</Text>
              <Text style={styles.metaValue}>{formatDateTime(event.startDate)}</Text>
            </View>
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>Time</Text>
              <Text style={styles.metaValue}>
                {formatTime(event.startDate)} - {formatTime(event.endDate)}
              </Text>
            </View>
          </View>

          {event.venue?.name && (
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>Location</Text>
              <Text style={styles.metaValue}>{event.venue.name}</Text>
            </View>
          )}

          {/* Capacity badge */}
          <View style={styles.capacityRow}>
            <Badge
              variant={event.isSoldOut ? 'destructive' : event.availableSpots != null && event.availableSpots <= 20 ? 'warning' : 'default'}
              label={spotsInfo}
            />
            {tickets.length > 0 && (
              <Text style={styles.priceText}>{getPriceDisplay(tickets)}</Text>
            )}
          </View>

          {/* About */}
          {event.description && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>About</Text>
              <Card style={styles.descCard}>
                <Text style={styles.descText}>{event.description}</Text>
              </Card>
            </View>
          )}

          {/* Agenda */}
          {sessions.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Agenda</Text>
              {sessions.map((session) => (
                <Card key={session.id} style={styles.sessionCard}>
                  <View style={styles.sessionTimeCol}>
                    <Text style={styles.sessionTime}>
                      {formatTime(session.startTime)}
                    </Text>
                  </View>
                  <View style={styles.sessionInfo}>
                    <Text style={styles.sessionTitle}>{session.title}</Text>
                    {session.speakers.length > 0 && (
                      <Text style={styles.sessionSpeakers}>
                        {session.speakers.map((s) => s.name).join(', ')}
                      </Text>
                    )}
                    <Text style={styles.sessionRange}>
                      {formatTime(session.startTime)} - {formatTime(session.endTime)}
                    </Text>
                  </View>
                </Card>
              ))}
            </View>
          )}

          {/* Spacer for bottom CTA */}
          <View style={styles.bottomSpacer} />
        </View>
      </ScrollView>

      {/* Fixed bottom CTA */}
      <View style={styles.bottomBar}>
        <View>
          {tickets.length > 0 && (
            <Text style={styles.bottomPrice}>{getPriceDisplay(tickets)}</Text>
          )}
          <Text style={styles.bottomSpots}>{spotsInfo}</Text>
        </View>
        <Button
          title={event.isSoldOut ? 'Sold Out' : 'Get Tickets'}
          onPress={() => navigation.navigate('TicketSelection', { eventId })}
          size="lg"
          disabled={event.isSoldOut}
          style={{ minWidth: 140 }}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  errorTitle: { ...typography.h3, color: colors.foreground, marginBottom: 16 },
  hero: { width: SCREEN_WIDTH, height: HERO_HEIGHT },
  heroPlaceholder: { backgroundColor: colors.primary.navy, justifyContent: 'center', alignItems: 'center' },
  heroPlaceholderText: { fontSize: 48, fontWeight: '800', color: colors.primary.gold },
  backButton: {
    position: 'absolute',
    top: 12,
    left: 16,
    backgroundColor: 'rgba(0,0,0,0.5)',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
  },
  backButtonText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  content: { padding: 24 },
  eventTitle: { ...typography.h1, color: colors.foreground, marginBottom: 16 },
  metaRow: { flexDirection: 'row', gap: 24, marginBottom: 12 },
  metaItem: { marginBottom: 8 },
  metaLabel: { ...typography.caption, color: colors.neutral[400], marginBottom: 2 },
  metaValue: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  capacityRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8, marginBottom: 24 },
  priceText: { ...typography.h3, color: colors.primary.gold },
  section: { marginBottom: 24 },
  sectionTitle: {
    ...typography.h3,
    color: colors.foreground,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 12,
  },
  descCard: { padding: 16 },
  descText: { ...typography.body, color: colors.neutral[600], lineHeight: 24 },
  sessionCard: { flexDirection: 'row', padding: 12, marginBottom: 8 },
  sessionTimeCol: { width: 70, justifyContent: 'center' },
  sessionTime: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '700' },
  sessionInfo: { flex: 1 },
  sessionTitle: { ...typography.body, color: colors.foreground, fontWeight: '600', marginBottom: 2 },
  sessionSpeakers: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 2 },
  sessionRange: { ...typography.caption, color: colors.neutral[400] },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    paddingBottom: 32,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  bottomPrice: { ...typography.h4, color: colors.foreground },
  bottomSpots: { ...typography.caption, color: colors.neutral[500] },
  bottomSpacer: { height: 80 },
});
