import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { SessionSocketProvider } from '@/context/SessionSocketContext';
import { useSessionReactions } from '@/hooks/useSessionReactions';
import { FloatingReactions } from '@/components/session/FloatingReactions';
import { ReactionBar } from '@/components/session/ReactionBar';
import { SessionVideoPlayer } from '@/components/video/SessionVideoPlayer';
import { ChatTab } from './ChatTab';
import { QATab } from './QATab';
import { PollsTab } from './PollsTab';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type NavProp = NativeStackNavigationProp<HomeStackParamList, 'SessionLive'>;
type RoutePropType = RouteProp<HomeStackParamList, 'SessionLive'>;

type TabKey = 'video' | 'chat' | 'qa' | 'polls';

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'video', label: 'Video', icon: '📹' },
  { key: 'chat', label: 'Chat', icon: '💬' },
  { key: 'qa', label: 'Q&A', icon: '❓' },
  { key: 'polls', label: 'Polls', icon: '📊' },
];

function SessionLiveContent({ sessionTitle, sessionId, eventId }: { sessionTitle: string; sessionId: string; eventId: string }) {
  const [activeTab, setActiveTab] = useState<TabKey>('video');
  const navigation = useNavigation<NavProp>();
  const {
    floatingEmojis,
    reactionsOpen,
    sendReaction,
  } = useSessionReactions();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <View style={styles.liveIndicator}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>LIVE</Text>
          </View>
          <Text style={styles.headerTitle} numberOfLines={1} accessibilityRole="header">
            {sessionTitle}
          </Text>
        </View>
        <View style={styles.headerSpacer} />
      </View>

      {/* Tab bar */}
      <View style={styles.tabBar}>
        {TABS.map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            onPress={() => setActiveTab(tab.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: activeTab === tab.key }}
            accessibilityLabel={tab.label}
          >
            <Text style={styles.tabIcon}>{tab.icon}</Text>
            <Text style={[styles.tabLabel, activeTab === tab.key && styles.tabLabelActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Tab content */}
      <View style={styles.content}>
        {activeTab === 'video' && <SessionVideoPlayer sessionId={sessionId} eventId={eventId} />}
        {activeTab === 'chat' && <ChatTab />}
        {activeTab === 'qa' && <QATab />}
        {activeTab === 'polls' && <PollsTab />}
      </View>

      {/* Floating reactions overlay */}
      <FloatingReactions emojis={floatingEmojis} />

      {/* Reaction bar */}
      {reactionsOpen !== false && (
        <ReactionBar onReaction={sendReaction} />
      )}
    </SafeAreaView>
  );
}

export function SessionLiveScreen() {
  const route = useRoute<RoutePropType>();
  const { eventId, sessionId, sessionTitle, chatOpen, qaOpen, pollsOpen, reactionsOpen } = route.params;

  return (
    <SessionSocketProvider
      sessionId={sessionId}
      eventId={eventId}
      initialChatOpen={chatOpen}
      initialQaOpen={qaOpen}
      initialPollsOpen={pollsOpen}
      initialReactionsOpen={reactionsOpen}
    >
      <SessionLiveContent sessionTitle={sessionTitle} sessionId={sessionId} eventId={eventId} />
    </SessionSocketProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.primary.navy,
  },
  backBtn: { width: 60 },
  backText: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '600' },
  headerCenter: { flex: 1, alignItems: 'center' },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 2,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#EF4444',
  },
  liveText: {
    ...typography.caption,
    fontWeight: '700',
    color: '#EF4444',
    letterSpacing: 1,
  },
  headerTitle: {
    ...typography.bodySmall,
    color: '#FFFFFF',
    fontWeight: '600',
  },
  headerSpacer: { width: 60 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 10,
    gap: 4,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: colors.primary.gold,
  },
  tabIcon: { fontSize: 16 },
  tabLabel: {
    ...typography.label,
    color: colors.neutral[500],
  },
  tabLabelActive: {
    color: colors.primary.navy,
    fontWeight: '700',
  },
  content: { flex: 1 },
});
