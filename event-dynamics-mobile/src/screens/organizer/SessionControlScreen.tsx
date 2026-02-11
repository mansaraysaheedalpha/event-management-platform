import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation } from '@apollo/client/react';
import * as Haptics from 'expo-haptics';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import {
  GET_SESSION_BY_ID_QUERY,
  GO_LIVE_SESSION_MUTATION,
  END_SESSION_MUTATION,
  TOGGLE_SESSION_CHAT_MUTATION,
  TOGGLE_SESSION_QA_MUTATION,
  TOGGLE_SESSION_POLLS_MUTATION,
  TOGGLE_SESSION_REACTIONS_MUTATION,
} from '@/graphql';
import { Card, Badge, Button, SessionDetailSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'SessionControl'>;
type Route = RouteProp<OrganizerStackParamList, 'SessionControl'>;

interface Session {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  chatOpen: boolean;
  qaOpen: boolean;
  pollsOpen: boolean;
  reactionsOpen: boolean;
  chatEnabled: boolean;
  qaEnabled: boolean;
  pollsEnabled: boolean;
  reactionsEnabled: boolean;
  speakers?: Array<{ id: string; name: string }>;
}

interface SessionResponse {
  session: Session;
}

function getSessionStatus(session: Session): string {
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

export function SessionControlScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sessionId } = route.params;

  const { data, loading, refetch } = useQuery<SessionResponse>(
    GET_SESSION_BY_ID_QUERY,
    {
      variables: { id: sessionId },
      fetchPolicy: 'cache-and-network',
      pollInterval: 10000,
    },
  );

  const [goLive, { loading: goingLive }] = useMutation<{ goLiveSession: { id: string; status: string } }>(
    GO_LIVE_SESSION_MUTATION,
  );
  const [endSession, { loading: ending }] = useMutation<{ endSession: { id: string; status: string } }>(
    END_SESSION_MUTATION,
  );
  const [toggleChat] = useMutation<{ toggleSessionChat: { id: string; chatOpen: boolean } }>(
    TOGGLE_SESSION_CHAT_MUTATION,
  );
  const [toggleQA] = useMutation<{ toggleSessionQA: { id: string; qaOpen: boolean } }>(
    TOGGLE_SESSION_QA_MUTATION,
  );
  const [togglePolls] = useMutation<{ toggleSessionPolls: { id: string; pollsOpen: boolean } }>(
    TOGGLE_SESSION_POLLS_MUTATION,
  );
  const [toggleReactions] = useMutation<{ toggleSessionReactions: { id: string; reactionsOpen: boolean } }>(
    TOGGLE_SESSION_REACTIONS_MUTATION,
  );

  const session = data?.session;
  const status = session ? getSessionStatus(session) : null;

  const handleGoLive = useCallback(() => {
    Alert.alert('Go Live', 'Start this session now?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Go Live',
        style: 'default',
        onPress: async () => {
          await goLive({ variables: { id: sessionId } });
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          refetch();
        },
      },
    ]);
  }, [goLive, sessionId, refetch]);

  const handleEndSession = useCallback(() => {
    Alert.alert('End Session', 'Are you sure you want to end this session?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'End Session',
        style: 'destructive',
        onPress: async () => {
          await endSession({ variables: { id: sessionId } });
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          refetch();
        },
      },
    ]);
  }, [endSession, sessionId, refetch]);

  const handleToggle = useCallback(
    async (
      type: 'chat' | 'qa' | 'polls' | 'reactions',
      currentValue: boolean,
    ) => {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      const newValue = !currentValue;

      switch (type) {
        case 'chat':
          await toggleChat({ variables: { id: sessionId, open: newValue } });
          break;
        case 'qa':
          await toggleQA({ variables: { id: sessionId, open: newValue } });
          break;
        case 'polls':
          await togglePolls({ variables: { id: sessionId, open: newValue } });
          break;
        case 'reactions':
          await toggleReactions({ variables: { id: sessionId, open: newValue } });
          break;
      }
      refetch();
    },
    [sessionId, toggleChat, toggleQA, togglePolls, toggleReactions, refetch],
  );

  if (loading && !data) {
    return <SessionDetailSkeleton />;
  }

  if (!session) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>Session not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>

        {/* Session info */}
        <View style={styles.sessionInfo}>
          <Badge
            variant={status === 'LIVE' ? 'success' : status === 'UPCOMING' ? 'info' : 'default'}
            label={status ?? 'UNKNOWN'}
          />
          <Text style={styles.sessionTitle}>{session.title}</Text>
          <Text style={styles.sessionTime}>
            {formatTime(session.startTime)} – {formatTime(session.endTime)}
          </Text>
          {session.speakers && session.speakers.length > 0 && (
            <Text style={styles.sessionSpeakers}>
              Speakers: {session.speakers.map((s) => s.name).join(', ')}
            </Text>
          )}
        </View>

        {/* Go Live / End Session */}
        <View style={styles.actionButtons}>
          {status === 'UPCOMING' && (
            <Button
              title="Go Live Now"
              onPress={handleGoLive}
              loading={goingLive}
              variant="primary"
              fullWidth
            />
          )}
          {status === 'LIVE' && (
            <Button
              title="End Session"
              onPress={handleEndSession}
              loading={ending}
              variant="destructive"
              fullWidth
            />
          )}
        </View>

        {/* Feature toggles */}
        <Text style={styles.sectionHeader}>Feature Controls</Text>

        <Card style={styles.toggleCard}>
          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Chat</Text>
              <Text style={styles.toggleDesc}>
                {session.chatEnabled ? 'Enabled' : 'Disabled by config'}
              </Text>
            </View>
            <Switch
              value={session.chatOpen}
              onValueChange={() => handleToggle('chat', session.chatOpen)}
              disabled={!session.chatEnabled}
              trackColor={{ false: colors.neutral[700], true: colors.success }}
              thumbColor={colors.neutral[100]}
            />
          </View>

          <View style={styles.divider} />

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Q&A</Text>
              <Text style={styles.toggleDesc}>
                {session.qaEnabled ? 'Enabled' : 'Disabled by config'}
              </Text>
            </View>
            <Switch
              value={session.qaOpen}
              onValueChange={() => handleToggle('qa', session.qaOpen)}
              disabled={!session.qaEnabled}
              trackColor={{ false: colors.neutral[700], true: colors.success }}
              thumbColor={colors.neutral[100]}
            />
          </View>

          <View style={styles.divider} />

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Polls</Text>
              <Text style={styles.toggleDesc}>
                {session.pollsEnabled ? 'Enabled' : 'Disabled by config'}
              </Text>
            </View>
            <Switch
              value={session.pollsOpen}
              onValueChange={() => handleToggle('polls', session.pollsOpen)}
              disabled={!session.pollsEnabled}
              trackColor={{ false: colors.neutral[700], true: colors.success }}
              thumbColor={colors.neutral[100]}
            />
          </View>

          <View style={styles.divider} />

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Reactions</Text>
              <Text style={styles.toggleDesc}>
                {session.reactionsEnabled ? 'Enabled' : 'Disabled by config'}
              </Text>
            </View>
            <Switch
              value={session.reactionsOpen}
              onValueChange={() => handleToggle('reactions', session.reactionsOpen)}
              disabled={!session.reactionsEnabled}
              trackColor={{ false: colors.neutral[700], true: colors.success }}
              thumbColor={colors.neutral[100]}
            />
          </View>
        </Card>

        <View style={styles.bottomSpacer} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  backButton: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 4 },
  backText: { ...typography.body, color: colors.primary.gold, fontWeight: '600' },
  sessionInfo: { paddingHorizontal: 24, paddingTop: 12, gap: 6 },
  sessionTitle: { ...typography.h2, color: colors.foreground },
  sessionTime: { ...typography.body, color: colors.neutral[500] },
  sessionSpeakers: { ...typography.bodySmall, color: colors.neutral[400] },
  actionButtons: { paddingHorizontal: 24, paddingTop: 20, gap: 12 },
  sectionHeader: {
    ...typography.h4,
    color: colors.foreground,
    paddingHorizontal: 24,
    marginTop: 28,
    marginBottom: 12,
  },
  toggleCard: { marginHorizontal: 24, padding: 4 },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 12,
  },
  toggleInfo: { flex: 1 },
  toggleLabel: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  toggleDesc: { ...typography.caption, color: colors.neutral[500], marginTop: 2 },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginHorizontal: 12 },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  emptyTitle: { ...typography.h3, color: colors.foreground },
  bottomSpacer: { height: 40 },
});
