import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { Image } from 'expo-image';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import {
  GET_EVENT_BY_ID_QUERY,
  GET_SESSIONS_BY_EVENT_QUERY,
} from '@/graphql';
import { Card, Badge, SessionDetailSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'OrganizerEventDetail'>;
type Route = RouteProp<OrganizerStackParamList, 'OrganizerEventDetail'>;

interface Event {
  id: string;
  name: string;
  status: string;
  startDate: string;
  endDate: string;
  registrationsCount: number;
  maxAttendees?: number;
  imageUrl?: string;
  eventType?: string;
  description?: string;
}

interface Session {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  status: string;
  chatOpen: boolean;
  qaOpen: boolean;
  pollsOpen: boolean;
  reactionsOpen: boolean;
  speakers?: Array<{ id: string; name: string }>;
}

interface EventResponse {
  event: Event;
}

interface SessionsResponse {
  sessionsByEvent: Session[];
}

function getSessionDisplayStatus(session: Session): string {
  const now = new Date();
  const start = new Date(session.startTime);
  const end = new Date(session.endTime);
  if (now >= start && now <= end) return 'LIVE';
  if (now < start) return 'UPCOMING';
  return 'ENDED';
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const QUICK_ACTIONS = [
  { key: 'LiveMonitor', label: 'Live Monitor', icon: '📡' },
  { key: 'CheckInScanner', label: 'Check-In', icon: '📷' },
  { key: 'IncidentList', label: 'Incidents', icon: '🚨' },
  { key: 'AnalyticsSnapshot', label: 'Analytics', icon: '📊' },
] as const;

export function OrganizerEventDetailScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { eventId } = route.params;

  const { data: eventData, loading: eventLoading, refetch: refetchEvent } =
    useQuery<EventResponse>(GET_EVENT_BY_ID_QUERY, {
      variables: { id: eventId },
      fetchPolicy: 'cache-and-network',
    });

  const { data: sessionsData, loading: sessionsLoading, refetch: refetchSessions } =
    useQuery<SessionsResponse>(GET_SESSIONS_BY_EVENT_QUERY, {
      variables: { eventId },
      fetchPolicy: 'cache-and-network',
    });

  const event = eventData?.event;
  const sessions = sessionsData?.sessionsByEvent ?? [];
  const loading = eventLoading || sessionsLoading;

  const handleRefresh = useCallback(() => {
    refetchEvent();
    refetchSessions();
  }, [refetchEvent, refetchSessions]);

  const handleQuickAction = useCallback(
    (action: typeof QUICK_ACTIONS[number]['key']) => {
      navigation.navigate(action, { eventId });
    },
    [navigation, eventId],
  );

  const handleSessionPress = useCallback(
    (sessionId: string) => {
      navigation.navigate('SessionControl', { eventId, sessionId });
    },
    [navigation, eventId],
  );

  const handleBack = useCallback(() => {
    navigation.goBack();
  }, [navigation]);

  if (loading && !eventData) {
    return <SessionDetailSkeleton />;
  }

  if (!event) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>Event not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Sort sessions: LIVE first, then UPCOMING, then ENDED
  const sortedSessions = [...sessions].sort((a, b) => {
    const order = { LIVE: 0, UPCOMING: 1, ENDED: 2 };
    const aStatus = getSessionDisplayStatus(a);
    const bStatus = getSessionDisplayStatus(b);
    return (order[aStatus as keyof typeof order] ?? 2) - (order[bStatus as keyof typeof order] ?? 2);
  });

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={handleRefresh} tintColor={colors.primary.gold} />
        }
      >
        {/* Back button */}
        <TouchableOpacity onPress={handleBack} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>

        {/* Event header */}
        <View style={styles.eventHeader}>
          {event.imageUrl ? (
            <Image
              source={{ uri: event.imageUrl }}
              style={styles.eventImage}
              contentFit="cover"
              placeholder={{ blurhash: imageConfig.defaultBlurhash }}
              cachePolicy={imageConfig.cachePolicy}
              transition={imageConfig.transition}
            />
          ) : (
            <View style={[styles.eventImage, styles.eventImagePlaceholder]}>
              <Text style={styles.eventImageText}>ED</Text>
            </View>
          )}
          <View style={styles.eventMeta}>
            <Badge
              variant={event.status === 'LIVE' ? 'success' : event.status === 'PUBLISHED' ? 'info' : 'default'}
              label={event.status}
            />
            <Text style={styles.eventTitle}>{event.name}</Text>
            <Text style={styles.eventDate}>{formatDate(event.startDate)}</Text>
            <Text style={styles.eventAttendees}>
              {event.registrationsCount}
              {event.maxAttendees ? ` / ${event.maxAttendees}` : ''} registered
            </Text>
          </View>
        </View>

        {/* Quick actions */}
        <Text style={styles.sectionHeader}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          {QUICK_ACTIONS.map((action) => (
            <TouchableOpacity
              key={action.key}
              style={styles.actionButton}
              onPress={() => handleQuickAction(action.key)}
              activeOpacity={0.7}
            >
              <Text style={styles.actionIcon}>{action.icon}</Text>
              <Text style={styles.actionLabel}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Sessions */}
        <Text style={styles.sectionHeader}>Sessions ({sessions.length})</Text>
        {sortedSessions.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyText}>No sessions for this event.</Text>
          </Card>
        ) : (
          sortedSessions.map((session) => {
            const displayStatus = getSessionDisplayStatus(session);
            const isLive = displayStatus === 'LIVE';
            return (
              <TouchableOpacity
                key={session.id}
                onPress={() => handleSessionPress(session.id)}
                activeOpacity={0.8}
              >
                <Card style={isLive ? { ...styles.sessionCard, borderColor: colors.success, borderWidth: 2 } : styles.sessionCard}>
                  <View style={styles.sessionHeader}>
                    <Badge
                      variant={isLive ? 'success' : displayStatus === 'UPCOMING' ? 'info' : 'default'}
                      label={displayStatus}
                    />
                    <Text style={styles.sessionTime}>
                      {formatTime(session.startTime)} – {formatTime(session.endTime)}
                    </Text>
                  </View>
                  <Text style={styles.sessionTitle}>{session.title}</Text>
                  {session.speakers && session.speakers.length > 0 && (
                    <Text style={styles.sessionSpeakers}>
                      {session.speakers.map((s) => s.name).join(', ')}
                    </Text>
                  )}
                  <View style={styles.featureRow}>
                    {session.chatOpen && <Badge variant="info" label="Chat" />}
                    {session.qaOpen && <Badge variant="info" label="Q&A" />}
                    {session.pollsOpen && <Badge variant="info" label="Polls" />}
                  </View>
                </Card>
              </TouchableOpacity>
            );
          })
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  backButton: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 4 },
  backText: { ...typography.body, color: colors.primary.gold, fontWeight: '600' },
  eventHeader: { flexDirection: 'row', paddingHorizontal: 24, paddingTop: 12, gap: 16 },
  eventImage: { width: 100, height: 100, borderRadius: 12 },
  eventImagePlaceholder: {
    backgroundColor: colors.primary.navy,
    justifyContent: 'center',
    alignItems: 'center',
  },
  eventImageText: { fontSize: 20, fontWeight: '800', color: colors.primary.gold },
  eventMeta: { flex: 1, gap: 4 },
  eventTitle: { ...typography.h3, color: colors.foreground },
  eventDate: { ...typography.bodySmall, color: colors.neutral[500] },
  eventAttendees: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '600' },
  sectionHeader: {
    ...typography.h4,
    color: colors.foreground,
    paddingHorizontal: 24,
    marginTop: 24,
    marginBottom: 12,
  },
  actionsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    gap: 12,
  },
  actionButton: {
    flex: 1,
    backgroundColor: colors.primary.navy,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    gap: 6,
  },
  actionIcon: { fontSize: 24 },
  actionLabel: { ...typography.caption, color: colors.neutral[200], fontWeight: '600' },
  sessionCard: { marginHorizontal: 24, marginBottom: 12, padding: 14 },
  sessionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  sessionTime: { ...typography.caption, color: colors.neutral[400] },
  sessionTitle: { ...typography.body, color: colors.foreground, fontWeight: '700', marginBottom: 4 },
  sessionSpeakers: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 6 },
  featureRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  emptyCard: { marginHorizontal: 24, padding: 24, alignItems: 'center' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  emptyTitle: { ...typography.h3, color: colors.foreground },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  bottomSpacer: { height: 40 },
});
