// Direct messages screen — full conversation list with search and new message
import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  Pressable,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, typography, spacing } from '@/theme';
import { ConversationItem } from '@/components/networking/ConversationItem';
import { useSharedDirectMessages } from '@/context/DirectMessagesContext';
import type { NetworkingStackParamList } from '@/navigation/types';
import type { Conversation } from '@/types/networking';

type Nav = NativeStackNavigationProp<NetworkingStackParamList, 'DirectMessages'>;

export function DirectMessagesScreen() {
  const navigation = useNavigation<Nav>();
  const [searchQuery, setSearchQuery] = useState('');

  const {
    conversations,
    isConnected,
    setActiveConversation,
  } = useSharedDirectMessages();

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter(c => {
      const name = `${c.recipient.firstName} ${c.recipient.lastName}`.toLowerCase();
      return name.includes(q);
    });
  }, [conversations, searchQuery]);

  const handleConversationPress = useCallback((conv: Conversation) => {
    setActiveConversation(conv);
    navigation.navigate('Conversation', {
      userId: conv.recipientId,
      userName: `${conv.recipient.firstName} ${conv.recipient.lastName}`,
    });
  }, [navigation, setActiveConversation]);

  const renderConversation = useCallback(({ item }: { item: Conversation }) => (
    <ConversationItem
      conversation={item}
      onPress={handleConversationPress}
    />
  ), [handleConversationPress]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>{'‹'}</Text>
        </Pressable>
        <Text style={styles.title}>Messages</Text>
        <View style={styles.statusDot}>
          <View style={[styles.dot, isConnected ? styles.dotOnline : styles.dotOffline]} />
        </View>
      </View>

      <View style={styles.searchBar}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search conversations..."
          placeholderTextColor={colors.neutral[400]}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {filteredConversations.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyIcon}>{'💬'}</Text>
          <Text style={styles.emptyTitle}>
            {searchQuery ? 'No results' : 'No messages yet'}
          </Text>
          <Text style={styles.emptyText}>
            {searchQuery
              ? 'Try a different search term'
              : 'Connect with attendees to start chatting'}
          </Text>
        </View>
      ) : (
        <FlashList
          data={filteredConversations}
          keyExtractor={item => item.id}
          renderItem={renderConversation}
          estimatedItemSize={72}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  backBtn: {
    padding: spacing.xs,
  },
  backText: {
    fontSize: 28,
    color: colors.primary.navy,
    fontWeight: '300',
    lineHeight: 28,
  },
  title: {
    ...typography.h2,
    color: colors.foreground,
    flex: 1,
  },
  statusDot: {
    padding: spacing.xs,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  dotOnline: {
    backgroundColor: colors.success,
  },
  dotOffline: {
    backgroundColor: colors.neutral[300],
  },
  searchBar: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.sm,
  },
  searchInput: {
    backgroundColor: colors.neutral[100],
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    ...typography.body,
    color: colors.foreground,
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
  },
});
