import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { GET_SESSION_BY_ID_QUERY } from '@/graphql/events.graphql';
import { Card, Badge, Button, SessionDetailSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type SessionNav = NativeStackNavigationProp<HomeStackParamList, 'SessionDetail'>;
type SessionRoute = RouteProp<HomeStackParamList, 'SessionDetail'>;

interface Speaker {
  id: string;
  name: string;
  userId?: string;
}

interface SessionData {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  sessionType: string;
  chatEnabled: boolean;
  qaEnabled: boolean;
  pollsEnabled: boolean;
  reactionsEnabled: boolean;
  breakoutEnabled: boolean;
  chatOpen: boolean;
  qaOpen: boolean;
  pollsOpen: boolean;
  reactionsOpen: boolean;
  streamingUrl?: string;
  recordingUrl?: string;
  broadcastOnly: boolean;
  speakers: Speaker[];
}

interface SessionResponse {
  session: SessionData;
}

function getSessionStatus(session: SessionData): 'live' | 'upcoming' | 'ended' {
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

function formatFullDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

function getDurationMinutes(start: string, end: string): number {
  return Math.round(
    (new Date(end).getTime() - new Date(start).getTime()) / 60000,
  );
}

export function SessionDetailScreen() {
  const navigation = useNavigation<SessionNav>();
  const route = useRoute<SessionRoute>();
  const { sessionId, eventId } = route.params;

  const { data, loading } = useQuery<SessionResponse>(GET_SESSION_BY_ID_QUERY, {
    variables: { id: sessionId },
  });

  if (loading && !data) {
    return <SessionDetailSkeleton />;
  }

  const session = data?.session;

  if (!session) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}>
          <Text style={styles.errorText}>Session not found</Text>
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

  const status = getSessionStatus(session);
  const duration = getDurationMinutes(session.startTime, session.endTime);
  const isLive = status === 'live';

  const features = [
    session.chatEnabled && { name: 'Chat', open: session.chatOpen },
    session.qaEnabled && { name: 'Q&A', open: session.qaOpen },
    session.pollsEnabled && { name: 'Polls', open: session.pollsOpen },
    session.reactionsEnabled && { name: 'Reactions', open: session.reactionsOpen },
    session.breakoutEnabled && { name: 'Breakout Rooms', open: true },
  ].filter(Boolean) as { name: string; open: boolean }[];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>

          <View style={styles.badgeRow}>
            {isLive && <Badge variant="success" label="Live Now" />}
            {status === 'upcoming' && <Badge variant="info" label="Upcoming" />}
            {status === 'ended' && <Badge variant="default" label="Ended" />}
            <Badge variant="default" label={session.sessionType} />
            <Badge variant="default" label={`${duration} min`} />
          </View>

          <Text style={styles.title} accessibilityRole="header">{session.title}</Text>

          {/* Time info */}
          <Card style={styles.timeCard}>
            <View style={styles.timeRow}>
              <View>
                <Text style={styles.timeLabel}>Date</Text>
                <Text style={styles.timeValue}>{formatFullDate(session.startTime)}</Text>
              </View>
              <View>
                <Text style={styles.timeLabel}>Time</Text>
                <Text style={styles.timeValue}>
                  {formatTime(session.startTime)} - {formatTime(session.endTime)}
                </Text>
              </View>
            </View>
          </Card>

          {/* Speakers */}
          {session.speakers.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Speakers</Text>
              {session.speakers.map((speaker) => (
                <Card key={speaker.id} style={styles.speakerCard}>
                  <View style={styles.speakerAvatar}>
                    <Text style={styles.speakerInitial}>
                      {speaker.name.charAt(0).toUpperCase()}
                    </Text>
                  </View>
                  <Text style={styles.speakerName}>{speaker.name}</Text>
                </Card>
              ))}
            </View>
          )}

          {/* Interactive Features */}
          {features.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Interactive Features</Text>
              <View style={styles.featureGrid}>
                {features.map((f) => (
                  <Card key={f.name} style={styles.featureCard}>
                    <Text style={styles.featureName}>{f.name}</Text>
                    <Badge
                      variant={f.open ? 'success' : 'default'}
                      label={f.open ? 'Open' : 'Closed'}
                    />
                  </Card>
                ))}
              </View>
            </View>
          )}

          {/* Actions */}
          <View style={styles.actions}>
            {isLive && (
              <Button
                title="Join Live Session"
                onPress={() => {
                  navigation.navigate('SessionLive', {
                    eventId,
                    sessionId: session.id,
                    sessionTitle: session.title,
                    chatOpen: session.chatOpen,
                    qaOpen: session.qaOpen,
                    pollsOpen: session.pollsOpen,
                    reactionsOpen: session.reactionsOpen,
                  });
                }}
                fullWidth
                size="lg"
              />
            )}
            {isLive && session.streamingUrl && (
              <Button
                title="Watch Stream"
                onPress={() => {
                  const url = session.streamingUrl;
                  if (url && (url.startsWith('https://') || url.startsWith('http://'))) {
                    Linking.openURL(url);
                  }
                }}
                fullWidth
                size="lg"
                variant="secondary"
              />
            )}
            {status === 'ended' && session.recordingUrl && (
              <Button
                title="Watch Recording"
                onPress={() => {
                  const url = session.recordingUrl;
                  if (url && (url.startsWith('https://') || url.startsWith('http://'))) {
                    Linking.openURL(url);
                  }
                }}
                fullWidth
                size="lg"
                variant="secondary"
              />
            )}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  errorText: { ...typography.h3, color: colors.foreground, marginBottom: 16 },
  header: { padding: 24 },
  backBtn: { marginBottom: 16 },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  badgeRow: { flexDirection: 'row', gap: 8, marginBottom: 12, flexWrap: 'wrap' },
  title: { ...typography.h1, color: colors.foreground, marginBottom: 16 },
  timeCard: { padding: 16, marginBottom: 24 },
  timeRow: { flexDirection: 'row', justifyContent: 'space-between' },
  timeLabel: { ...typography.caption, color: colors.neutral[400], marginBottom: 2 },
  timeValue: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  section: { marginBottom: 24 },
  sectionTitle: {
    ...typography.h3,
    color: colors.foreground,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 12,
  },
  speakerCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, marginBottom: 8 },
  speakerAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary.navy,
    justifyContent: 'center',
    alignItems: 'center',
  },
  speakerInitial: { color: colors.primary.gold, fontSize: 16, fontWeight: '700' },
  speakerName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  featureGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  featureCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    width: '48%',
    flexGrow: 1,
  },
  featureName: { ...typography.bodySmall, color: colors.foreground, fontWeight: '600' },
  actions: { marginTop: 8, gap: 12 },
});
