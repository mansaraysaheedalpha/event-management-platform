// Individual conversation / DM chat screen
import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  Pressable,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, typography, spacing } from '@/theme';
import { Avatar } from '@/components/ui';
import { MessageBubble } from '@/components/networking/MessageBubble';
import { useSharedDirectMessages } from '@/context/DirectMessagesContext';
import { useAuthStore } from '@/store/auth.store';
import type { NetworkingStackParamList } from '@/navigation/types';
import type { DirectMessage } from '@/types/networking';

type Nav = NativeStackNavigationProp<NetworkingStackParamList, 'Conversation'>;
type Route = RouteProp<NetworkingStackParamList, 'Conversation'>;

const MAX_MESSAGE_LENGTH = 2000;

export function ConversationScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { userId, userName } = route.params;
  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlashList<DirectMessage>>(null);
  const { user } = useAuthStore();
  const currentUserId = user?.id || '';

  const {
    messages,
    isConnected,
    isTyping,
    sendMessage,
    markAsRead,
    retryMessage,
    activeConversation,
  } = useSharedDirectMessages();

  // Mark messages as read when viewing
  useEffect(() => {
    const unreadMessages = messages.filter(
      m => m.senderId !== currentUserId && !m.isRead,
    );
    unreadMessages.forEach(m => markAsRead(m.id));
  }, [messages, currentUserId, markAsRead]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages.length]);

  const handleSend = useCallback(() => {
    const text = inputText.trim();
    if (!text) return;
    sendMessage(userId, text);
    setInputText('');
  }, [inputText, userId, sendMessage]);

  const handleRetry = useCallback((messageId: string) => {
    retryMessage(messageId);
  }, [retryMessage]);

  const recipientTyping = activeConversation
    ? isTyping[activeConversation.id]
    : false;

  // Pre-compute which messages should show a date header
  const dateHeaderSet = useMemo(() => {
    const set = new Set<string>();
    let prevDate = '';
    for (const msg of messages) {
      const d = new Date(msg.timestamp).toLocaleDateString();
      if (d !== prevDate) {
        set.add(msg.id);
        prevDate = d;
      }
    }
    return set;
  }, [messages]);

  const renderMessage = useCallback(({ item }: { item: DirectMessage }) => {
    const showDateHeader = dateHeaderSet.has(item.id);
    return (
      <View>
        {showDateHeader && (
          <View style={styles.dateSeparator}>
            <Text style={styles.dateText}>
              {new Date(item.timestamp).toLocaleDateString()}
            </Text>
          </View>
        )}
        <MessageBubble
          message={item}
          isOwn={item.senderId === currentUserId}
          onRetry={handleRetry}
        />
      </View>
    );
  }, [dateHeaderSet, currentUserId, handleRetry]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>{'‹'}</Text>
        </Pressable>
        <Avatar name={userName} size={36} />
        <View style={styles.headerInfo}>
          <Text style={styles.headerName} numberOfLines={1}>{userName}</Text>
          {recipientTyping && <Text style={styles.typingText}>typing...</Text>}
          {!recipientTyping && isConnected && <Text style={styles.onlineText}>Online</Text>}
        </View>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        {/* Messages */}
        <FlashList
          ref={flatListRef}
          data={messages}
          keyExtractor={item => item.id}
          renderItem={renderMessage}
          estimatedItemSize={80}
          contentContainerStyle={styles.messageList}
          onContentSizeChange={() => {
            flatListRef.current?.scrollToEnd({ animated: false });
          }}
          ListEmptyComponent={
            <View style={styles.emptyChat}>
              <Text style={styles.emptyChatText}>
                Start a conversation with {userName}
              </Text>
            </View>
          }
        />

        {/* Typing indicator */}
        {recipientTyping && (
          <View style={styles.typingIndicator}>
            <Text style={styles.typingDots}>{'• • •'}</Text>
          </View>
        )}

        {/* Input */}
        <View style={styles.inputBar}>
          <TextInput
            style={styles.input}
            placeholder="Type a message..."
            placeholderTextColor={colors.neutral[400]}
            value={inputText}
            onChangeText={setInputText}
            multiline
            maxLength={MAX_MESSAGE_LENGTH}
            returnKeyType="default"
          />
          <Pressable
            style={[styles.sendBtn, !inputText.trim() && styles.sendBtnDisabled]}
            onPress={handleSend}
            disabled={!inputText.trim()}
          >
            <Text style={[styles.sendText, !inputText.trim() && styles.sendTextDisabled]}>
              Send
            </Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
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
  headerInfo: {
    flex: 1,
  },
  headerName: {
    ...typography.h4,
    color: colors.foreground,
  },
  typingText: {
    ...typography.caption,
    color: colors.primary.gold,
    fontStyle: 'italic',
  },
  onlineText: {
    ...typography.caption,
    color: colors.success,
  },
  messageList: {
    paddingVertical: spacing.sm,
    flexGrow: 1,
  },
  dateSeparator: {
    alignItems: 'center',
    marginVertical: spacing.md,
  },
  dateText: {
    ...typography.caption,
    color: colors.neutral[400],
    backgroundColor: colors.neutral[100],
    paddingHorizontal: spacing.md,
    paddingVertical: 2,
    borderRadius: 10,
    overflow: 'hidden',
  },
  emptyChat: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing['2xl'],
  },
  emptyChatText: {
    ...typography.body,
    color: colors.neutral[400],
    textAlign: 'center',
  },
  typingIndicator: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.xs,
  },
  typingDots: {
    ...typography.bodySmall,
    color: colors.neutral[400],
    fontWeight: '700',
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.sm,
  },
  input: {
    flex: 1,
    backgroundColor: colors.neutral[100],
    borderRadius: 20,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    ...typography.body,
    color: colors.foreground,
    maxHeight: 100,
  },
  sendBtn: {
    backgroundColor: colors.primary.navy,
    borderRadius: 20,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
  },
  sendBtnDisabled: {
    backgroundColor: colors.neutral[200],
  },
  sendText: {
    ...typography.label,
    color: '#FFFFFF',
  },
  sendTextDisabled: {
    color: colors.neutral[400],
  },
});
