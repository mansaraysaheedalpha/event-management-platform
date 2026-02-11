import React, { useMemo, useCallback } from 'react';
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
import { GET_ATTENDEE_EVENT_DETAILS_QUERY } from '@/graphql/attendee.graphql';
import { Card, Badge, Button, SessionDetailSkeleton } from '@/components/ui';
import { EventHubGamification } from '@/components/gamification/EventHubGamification';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type HubNav = NativeStackNavigationProp<HomeStackParamList, 'EventHub'>;
type HubRoute = RouteProp<HomeStackParamList, 'EventHub'>;

interface Speaker {
  id: string;
  name: string;
  userId?: string;
}

interface Session {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  status: string;
  sessionType: string;
  chatEnabled: boolean;
  qaEnabled: boolean;
  pollsEnabled: boolean;
  reactionsEnabled: boolean;
  speakers: Speaker[];
}

interface EventVenue {
  id: string;
  name: string;
  address?: string;
}

interface EventDetail {
  id: string;
  name: string;
  description?: string;
  startDate: string;
  endDate: string;
  status: string;
  imageUrl?: string;
  eventType?: string;
  venue?: EventVenue;
}

interface Registration {
  id: string;
  status: string;
  ticketCode: string;
  checkedInAt?: string;
}

interface AttendeeEventResponse {
  myRegistrationForEvent: Registration;
  event: EventDetail;
  publicSessionsByEvent: Session[];
}

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const HERO_HEIGHT = SCREEN_WIDTH * 0.45;

function getSessionStatus(session: Session): 'live' | 'upcoming' | 'ended' {
  const now = new Date();
  const start = new Date(session.startTime);
  const end = new Date(session.endTime);
  if (now >= start && now <= end) return 'live';
  if (now < start) return 'upcoming';
  return 'ended';
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const SESSION_TYPE_COLORS: Record<string, string> = {
  MAINSTAGE: '#8B5CF6',
  BREAKOUT: '#10B981',
  WORKSHOP: '#F59E0B',
  NETWORKING: '#3B82F6',
  EXPO: '#EC4899',
};

function SessionCard({
  session,
  onPress,
}: {
  session: Session;
  onPress: () => void;
}) {
  const status = getSessionStatus(session);
  const isLive = status === 'live';
  const isEnded = status === 'ended';
  const typeColor = SESSION_TYPE_COLORS[session.sessionType] ?? colors.neutral[500];
  const features = [
    session.chatEnabled && 'Chat',
    session.qaEnabled && 'Q&A',
    session.pollsEnabled && 'Polls',
    session.reactionsEnabled && 'Reactions',
  ].filter(Boolean);

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8} accessibilityRole="button" accessibilityLabel={`Navigate to session ${session.title}`}>
      <Card
        style={[
          styles.sessionCard,
          isLive && styles.sessionCardLive,
          isEnded && styles.sessionCardEnded,
        ]}
      >
        <View style={styles.sessionHeader}>
          <View style={styles.sessionBadges}>
            {isLive && <Badge variant="success" label="Live" />}
            {status === 'upcoming' && <Badge variant="info" label="Upcoming" />}
            {isEnded && <Badge variant="default" label="Ended" />}
            <View style={[styles.typeBadge, { backgroundColor: `${typeColor}20` }]}>
              <Text style={[styles.typeBadgeText, { color: typeColor }]}>
                {session.sessionType}
              </Text>
            </View>
          </View>
          <Text style={styles.sessionTime}>
            {formatTime(session.startTime)} - {formatTime(session.endTime)}
          </Text>
        </View>

        <Text style={styles.sessionTitle}>{session.title}</Text>

        {session.speakers.length > 0 && (
          <Text style={styles.sessionSpeakers}>
            {session.speakers.map((s) => s.name).join(', ')}
          </Text>
        )}

        {features.length > 0 && (
          <View style={styles.featureRow}>
            {features.map((f) => (
              <View key={f as string} style={styles.featureChip}>
                <Text style={styles.featureChipText}>{f}</Text>
              </View>
            ))}
          </View>
        )}
      </Card>
    </TouchableOpacity>
  );
}

export function EventHubScreen() {
  const navigation = useNavigation<HubNav>();
  const route = useRoute<HubRoute>();
  const { eventId } = route.params;

  const { data, loading } = useQuery<AttendeeEventResponse>(
    GET_ATTENDEE_EVENT_DETAILS_QUERY,
    { variables: { eventId }, fetchPolicy: 'cache-and-network' },
  );

  const { liveSessions, upcomingSessions, pastSessions } = useMemo(() => {
    const sessions = data?.publicSessionsByEvent ?? [];
    const live: Session[] = [];
    const upcoming: Session[] = [];
    const past: Session[] = [];

    for (const s of sessions) {
      const status = getSessionStatus(s);
      if (status === 'live') live.push(s);
      else if (status === 'upcoming') upcoming.push(s);
      else past.push(s);
    }

    upcoming.sort(
      (a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime(),
    );
    past.sort(
      (a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime(),
    );

    return { liveSessions: live, upcomingSessions: upcoming, pastSessions: past };
  }, [data]);

  // First live session drives gamification (fallback to first session)
  const allSessions = data?.publicSessionsByEvent ?? [];
  const gamificationSessionId = liveSessions[0]?.id || allSessions[0]?.id || '';

  const navigateGamification = useCallback(
    (screen: 'GamificationHub' | 'Leaderboard' | 'Achievements' | 'Teams') => {
      if (gamificationSessionId) {
        navigation.navigate(screen, { eventId, sessionId: gamificationSessionId });
      }
    },
    [navigation, eventId, gamificationSessionId]
  );

  if (loading && !data) {
    return <SessionDetailSkeleton />;
  }

  const event = data?.event;
  const registration = data?.myRegistrationForEvent;

  if (!event) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <Text style={styles.errorText}>Event not found</Text>
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

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
            accessibilityLabel={`${event.name} event banner`}
          />
        ) : (
          <View style={[styles.hero, styles.heroPlaceholder]}>
            <Text style={styles.heroText}>ED</Text>
          </View>
        )}

        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()} accessibilityRole="button" accessibilityLabel="Go back">
          <Text style={styles.backBtnText}>Back</Text>
        </TouchableOpacity>

        <View style={styles.content}>
          <Text style={styles.eventTitle} accessibilityRole="header">{event.name}</Text>

          {/* Event type badge */}
          {event.eventType && (
            <Badge
              variant="info"
              label={event.eventType.replace(/_/g, ' ')}
            />
          )}

          {/* Info cards */}
          <View style={styles.infoRow}>
            <Card style={styles.infoCard}>
              <Text style={styles.infoLabel}>Date</Text>
              <Text style={styles.infoValue}>{formatDate(event.startDate)}</Text>
            </Card>
            <Card style={styles.infoCard}>
              <Text style={styles.infoLabel}>Time</Text>
              <Text style={styles.infoValue}>{formatTime(event.startDate)}</Text>
            </Card>
          </View>

          <View style={styles.infoRow}>
            {event.venue?.name ? (
              <Card style={styles.infoCard}>
                <Text style={styles.infoLabel}>Venue</Text>
                <Text style={styles.infoValue} numberOfLines={1}>{event.venue.name}</Text>
              </Card>
            ) : (
              <Card style={styles.infoCard}>
                <Text style={styles.infoLabel}>Format</Text>
                <Text style={styles.infoValue}>Online Event</Text>
              </Card>
            )}
            {registration && (
              <Card style={styles.infoCard}>
                <Text style={styles.infoLabel}>Ticket</Text>
                <Text style={styles.infoValue}>{registration.ticketCode}</Text>
              </Card>
            )}
          </View>

          {/* Quick actions */}
          <View style={styles.actionRow}>
            <Button
              title="Attendees"
              onPress={() => navigation.navigate('AttendeeList', { eventId })}
              variant="outline"
              size="sm"
              style={{ flex: 1 }}
            />
            <Button
              title="Expo Hall"
              onPress={() => navigation.navigate('ExpoHall', { eventId })}
              variant="outline"
              size="sm"
              style={{ flex: 1 }}
            />
          </View>

          {/* Gamification Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Gamification</Text>
            <EventHubGamification
              sessionId={gamificationSessionId}
              eventId={eventId}
              onOpenHub={() => navigateGamification('GamificationHub')}
              onOpenLeaderboard={() => navigateGamification('Leaderboard')}
              onOpenAchievements={() => navigateGamification('Achievements')}
              onOpenTeams={() => navigateGamification('Teams')}
            />
          </View>

          {/* Live Sessions */}
          {liveSessions.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Live Now</Text>
              {liveSessions.map((s) => (
                <SessionCard
                  key={s.id}
                  session={s}

                  onPress={() =>
                    navigation.navigate('SessionDetail', { eventId, sessionId: s.id })
                  }
                />
              ))}
            </View>
          )}

          {/* Upcoming Sessions */}
          {upcomingSessions.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Upcoming Sessions</Text>
              {upcomingSessions.map((s) => (
                <SessionCard
                  key={s.id}
                  session={s}

                  onPress={() =>
                    navigation.navigate('SessionDetail', { eventId, sessionId: s.id })
                  }
                />
              ))}
            </View>
          )}

          {/* Past Sessions */}
          {pastSessions.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Past Sessions</Text>
              {pastSessions.map((s) => (
                <SessionCard
                  key={s.id}
                  session={s}

                  onPress={() =>
                    navigation.navigate('SessionDetail', { eventId, sessionId: s.id })
                  }
                />
              ))}
            </View>
          )}

          {liveSessions.length === 0 &&
            upcomingSessions.length === 0 &&
            pastSessions.length === 0 && (
              <View style={styles.emptySection}>
                <Text style={styles.emptyText}>Agenda coming soon</Text>
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
  errorText: { ...typography.h3, color: colors.foreground, marginBottom: 16 },
  hero: { width: SCREEN_WIDTH, height: HERO_HEIGHT },
  heroPlaceholder: { backgroundColor: colors.primary.navy, justifyContent: 'center', alignItems: 'center' },
  heroText: { fontSize: 40, fontWeight: '800', color: colors.primary.gold },
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
  content: { padding: 24 },
  eventTitle: { ...typography.h1, color: colors.foreground, marginBottom: 8 },
  infoRow: { flexDirection: 'row', gap: 12, marginTop: 12 },
  infoCard: { flex: 1, padding: 12 },
  infoLabel: { ...typography.caption, color: colors.neutral[400], marginBottom: 2 },
  infoValue: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  actionRow: { flexDirection: 'row', gap: 12, marginTop: 16, marginBottom: 8 },
  section: { marginTop: 24 },
  sectionTitle: {
    ...typography.h3,
    color: colors.foreground,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 12,
  },
  sessionCard: { marginBottom: 12, padding: 14 },
  sessionCardLive: { borderLeftColor: colors.success, borderLeftWidth: 3 },
  sessionCardEnded: { opacity: 0.6 },
  sessionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  sessionBadges: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  typeBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  typeBadgeText: { ...typography.caption, fontWeight: '600', textTransform: 'capitalize' },
  sessionTime: { ...typography.caption, color: colors.neutral[400] },
  sessionTitle: { ...typography.body, color: colors.foreground, fontWeight: '700', marginBottom: 4 },
  sessionSpeakers: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 6 },
  featureRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  featureChip: {
    backgroundColor: colors.neutral[100],
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  featureChipText: { ...typography.caption, color: colors.neutral[600] },
  emptySection: { alignItems: 'center', paddingVertical: 40 },
  emptyText: { ...typography.body, color: colors.neutral[400] },
});
