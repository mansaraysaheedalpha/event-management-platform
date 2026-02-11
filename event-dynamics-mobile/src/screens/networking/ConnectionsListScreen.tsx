// Networking hub — main screen for the Networking tab
// Three top tabs: Connections, Messages, Discover

import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  TextInput,
  RefreshControl,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, typography, spacing } from '@/theme';
import { ScreenSkeleton, AttendeeRowSkeleton } from '@/components/ui';
import { ConnectionCard } from '@/components/networking/ConnectionCard';
import { ConversationItem } from '@/components/networking/ConversationItem';
import { useConnections } from '@/hooks/useConnections';
import { useSharedDirectMessages } from '@/context/DirectMessagesContext';
import { useAuthStore } from '@/store/auth.store';
import type { NetworkingStackParamList } from '@/navigation/types';
import type { Connection, Conversation } from '@/types/networking';

type Nav = NativeStackNavigationProp<NetworkingStackParamList, 'ConnectionsList'>;

type TabKey = 'connections' | 'messages' | 'discover';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'connections', label: 'Connections' },
  { key: 'messages', label: 'Messages' },
  { key: 'discover', label: 'Discover' },
];

export function ConnectionsListScreen() {
  const navigation = useNavigation<Nav>();
  const [activeTab, setActiveTab] = useState<TabKey>('connections');
  const [searchQuery, setSearchQuery] = useState('');
  const [connectionFilter, setConnectionFilter] = useState<'all' | 'pending' | 'strong'>('all');
  const { user } = useAuthStore();
  const currentUserId = user?.id || '';

  // Hooks
  const {
    connections,
    isLoading: connectionsLoading,
    error: connectionsError,
    strengthDistribution,
    fetchConnections,
  } = useConnections({ autoFetch: true });

  const {
    conversations,
    isConnected: dmConnected,
    getTotalUnreadCount,
    setActiveConversation,
  } = useSharedDirectMessages();

  const unreadCount = getTotalUnreadCount();

  // Connection filtering
  const filteredConnections = useMemo(() => {
    let list = connections;

    if (connectionFilter === 'pending') {
      list = list.filter(c => !c.followUpSent);
    } else if (connectionFilter === 'strong') {
      list = list.filter(c => c.strength === 'STRONG');
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(c => {
        const other = c.userA.id === currentUserId ? c.userB : c.userA;
        const name = `${other.firstName} ${other.lastName}`.toLowerCase();
        return name.includes(q) || (other.company?.toLowerCase().includes(q) ?? false);
      });
    }

    return list;
  }, [connections, connectionFilter, searchQuery, currentUserId]);

  // Navigation callbacks
  const handleConnectionPress = useCallback((conn: Connection) => {
    const other = conn.userA.id === currentUserId ? conn.userB : conn.userA;
    navigation.navigate('UserProfile', { userId: other.id });
  }, [currentUserId, navigation]);

  const handleMessage = useCallback((userId: string, userName: string) => {
    navigation.navigate('Conversation', { userId, userName });
  }, [navigation]);

  const handleFollowUp = useCallback((_connectionId: string) => {
    // No-op until follow-up flow is implemented
  }, []);

  const handleConversationPress = useCallback((conv: Conversation) => {
    setActiveConversation(conv);
    navigation.navigate('Conversation', {
      userId: conv.recipientId,
      userName: `${conv.recipient.firstName} ${conv.recipient.lastName}`,
    });
  }, [navigation, setActiveConversation]);

  const handleNewConversation = useCallback(() => {
    navigation.navigate('DirectMessages');
  }, [navigation]);

  const renderConnectionItem = useCallback(({ item }: { item: Connection }) => (
    <ConnectionCard
      connection={item}
      currentUserId={currentUserId}
      onPress={handleConnectionPress}
      onMessage={handleMessage}
      onFollowUp={handleFollowUp}
    />
  ), [currentUserId, handleConnectionPress, handleMessage, handleFollowUp]);

  const renderConversationItem = useCallback(({ item }: { item: Conversation }) => (
    <ConversationItem
      conversation={item}
      onPress={handleConversationPress}
    />
  ), [handleConversationPress]);

  // Render connection filters
  const renderConnectionFilters = () => (
    <View style={styles.filterRow}>
      {(['all', 'pending', 'strong'] as const).map(filter => (
        <Pressable
          key={filter}
          onPress={() => setConnectionFilter(filter)}
          style={[styles.filterChip, connectionFilter === filter && styles.filterChipActive]}
          accessibilityRole="button"
          accessibilityState={{ selected: connectionFilter === filter }}
          accessibilityLabel={`Filter by ${filter}`}
        >
          <Text style={[styles.filterText, connectionFilter === filter && styles.filterTextActive]}>
            {filter === 'all' ? `All (${connections.length})` :
             filter === 'pending' ? `Pending (${connections.filter(c => !c.followUpSent).length})` :
             `Strong (${strengthDistribution.STRONG})`}
          </Text>
        </Pressable>
      ))}
    </View>
  );

  // Render stats bar
  const renderStats = () => (
    <View style={styles.statsRow}>
      <View style={styles.statItem}>
        <Text style={styles.statValue}>{connections.length}</Text>
        <Text style={styles.statLabel}>Connections</Text>
      </View>
      <View style={styles.statDivider} />
      <View style={styles.statItem}>
        <Text style={styles.statValue}>{strengthDistribution.STRONG}</Text>
        <Text style={styles.statLabel}>Strong</Text>
      </View>
      <View style={styles.statDivider} />
      <View style={styles.statItem}>
        <Text style={styles.statValue}>{connections.filter(c => !c.followUpSent).length}</Text>
        <Text style={styles.statLabel}>Pending</Text>
      </View>
    </View>
  );

  // Render tab content
  const renderContent = () => {
    switch (activeTab) {
      case 'connections':
        if (connectionsLoading && connections.length === 0) {
          return <ScreenSkeleton count={6} ItemSkeleton={AttendeeRowSkeleton} header={false} />;
        }
        if (connections.length === 0) {
          return (
            <View style={styles.emptyState}>
              <Text style={styles.emptyIcon}>{'🤝'}</Text>
              <Text style={styles.emptyTitle}>No connections yet</Text>
              <Text style={styles.emptyText}>
                Start networking at events to build your professional connections
              </Text>
              <Pressable
                style={styles.emptyBtn}
                onPress={() => setActiveTab('discover')}
                accessibilityRole="button"
                accessibilityLabel="Discover People"
              >
                <Text style={styles.emptyBtnText}>Discover People</Text>
              </Pressable>
            </View>
          );
        }
        return (
          <>
            {renderStats()}
            <View style={styles.searchBar}>
              <TextInput
                style={styles.searchInput}
                placeholder="Search connections..."
                placeholderTextColor={colors.neutral[400]}
                value={searchQuery}
                onChangeText={setSearchQuery}
                accessibilityLabel="Search connections"
                accessibilityRole="search"
              />
            </View>
            {renderConnectionFilters()}
            <FlashList
              data={filteredConnections}
              keyExtractor={item => item.id}
              renderItem={renderConnectionItem}
              estimatedItemSize={72}
              contentContainerStyle={styles.listContent}
              refreshControl={
                <RefreshControl
                  refreshing={connectionsLoading}
                  onRefresh={fetchConnections}
                  tintColor={colors.primary.gold}
                />
              }
            />
          </>
        );

      case 'messages':
        if (conversations.length === 0) {
          return (
            <View style={styles.emptyState}>
              <Text style={styles.emptyIcon}>{'💬'}</Text>
              <Text style={styles.emptyTitle}>No messages yet</Text>
              <Text style={styles.emptyText}>
                Start a conversation with someone you've connected with
              </Text>
              <Pressable style={styles.emptyBtn} onPress={handleNewConversation} accessibilityRole="button" accessibilityLabel="New Message">
                <Text style={styles.emptyBtnText}>New Message</Text>
              </Pressable>
            </View>
          );
        }
        return (
          <FlashList
            data={conversations}
            keyExtractor={item => item.id}
            renderItem={renderConversationItem}
            estimatedItemSize={72}
            contentContainerStyle={styles.listContent}
          />
        );

      case 'discover':
        return (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>{'✨'}</Text>
            <Text style={styles.emptyTitle}>AI Recommendations</Text>
            <Text style={styles.emptyText}>
              Join an event to get personalized attendee recommendations powered by AI
            </Text>
          </View>
        );

      default:
        return null;
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">My Network</Text>
      </View>

      {/* Tab Bar */}
      <View style={styles.tabBar}>
        {TABS.map(tab => (
          <Pressable
            key={tab.key}
            onPress={() => setActiveTab(tab.key)}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            accessibilityRole="tab"
            accessibilityState={{ selected: activeTab === tab.key }}
            accessibilityLabel={tab.label}
          >
            <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
              {tab.label}
            </Text>
            {tab.key === 'messages' && unreadCount > 0 && (
              <View style={styles.unreadBadge}>
                <Text style={styles.unreadText}>
                  {unreadCount > 9 ? '9+' : unreadCount}
                </Text>
              </View>
            )}
          </Pressable>
        ))}
      </View>

      {/* Content */}
      <View style={styles.contentArea}>
        {renderContent()}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
  },
  title: {
    ...typography.h2,
    color: colors.foreground,
  },
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    gap: 6,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: colors.primary.gold,
  },
  tabText: {
    ...typography.label,
    color: colors.neutral[400],
  },
  tabTextActive: {
    color: colors.primary.navy,
    fontWeight: '700',
  },
  unreadBadge: {
    backgroundColor: colors.primary.gold,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 5,
  },
  unreadText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.primary.navy,
  },
  contentArea: {
    flex: 1,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    backgroundColor: colors.neutral[50],
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    ...typography.h3,
    color: colors.primary.navy,
  },
  statLabel: {
    ...typography.caption,
    color: colors.neutral[500],
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 32,
    backgroundColor: colors.border,
  },
  searchBar: {
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
  },
  searchInput: {
    backgroundColor: colors.neutral[100],
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    ...typography.body,
    color: colors.foreground,
  },
  filterRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.sm,
  },
  filterChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  filterChipActive: {
    backgroundColor: colors.primary.navy,
    borderColor: colors.primary.navy,
  },
  filterText: {
    ...typography.caption,
    color: colors.neutral[600],
  },
  filterTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    padding: spacing.base,
  },
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing['2xl'],
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.base,
  },
  emptyTitle: {
    ...typography.h3,
    color: colors.foreground,
    marginBottom: spacing.sm,
  },
  emptyText: {
    ...typography.body,
    color: colors.neutral[500],
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  emptyBtn: {
    backgroundColor: colors.primary.navy,
    borderRadius: 8,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
  },
  emptyBtnText: {
    ...typography.button,
    color: '#FFFFFF',
  },
});
