import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useBoothChat } from '@/hooks/useBoothChat';
import { Avatar, LoadingSpinner } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { BoothChatMessage } from '@/types/expo';

interface BoothChatScreenProps {
  boothId: string;
  eventId: string;
  boothName: string;
  onClose: () => void;
}

const ChatMessage = React.memo(function ChatMessage({
  message,
  isOwnMessage,
}: {
  message: BoothChatMessage;
  isOwnMessage: boolean;
}) {
  const time = new Date(message.createdAt).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });

  return (
    <View style={[styles.messageRow, isOwnMessage && styles.messageRowOwn]}>
      {!isOwnMessage && (
        <Avatar
          uri={message.senderAvatarUrl}
          name={message.senderName}
          size={28}
        />
      )}
      <View
        style={[
          styles.messageBubble,
          isOwnMessage ? styles.messageBubbleOwn : styles.messageBubbleOther,
          message.isStaff && !isOwnMessage && styles.messageBubbleStaff,
        ]}
      >
        {!isOwnMessage && (
          <View style={styles.senderRow}>
            <Text style={styles.senderName}>{message.senderName}</Text>
            {message.isStaff && (
              <View style={styles.staffBadge}>
                <Text style={styles.staffBadgeText}>Staff</Text>
              </View>
            )}
          </View>
        )}
        <Text
          style={[
            styles.messageText,
            isOwnMessage && styles.messageTextOwn,
          ]}
        >
          {message.text}
        </Text>
        <Text
          style={[
            styles.messageTime,
            isOwnMessage && styles.messageTimeOwn,
          ]}
        >
          {time}
        </Text>
      </View>
    </View>
  );
});

export function BoothChatScreen({
  boothId,
  eventId,
  boothName,
  onClose,
}: BoothChatScreenProps) {
  const {
    messages,
    hasMore,
    isConnected,
    isLoading,
    isSending,
    error,
    currentUserId,
    sendMessage,
    loadMore,
  } = useBoothChat({ boothId, eventId });

  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlatList<BoothChatMessage>>(null);

  const handleSend = useCallback(async () => {
    if (!inputText.trim() || isSending) return;
    const text = inputText;
    setInputText('');
    await sendMessage(text);
  }, [inputText, isSending, sendMessage]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages.length]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onClose}>
          <Text style={styles.closeText}>Close</Text>
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle} numberOfLines={1}>
            {boothName}
          </Text>
          {isConnected ? (
            <View style={styles.statusRow}>
              <View style={styles.onlineDot} />
              <Text style={styles.statusText}>Connected</Text>
            </View>
          ) : (
            <Text style={styles.statusTextOffline}>Connecting...</Text>
          )}
        </View>
        <View style={{ width: 50 }} />
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      <KeyboardAvoidingView
        style={styles.chatArea}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        {/* Messages */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <ChatMessage
              message={item}
              isOwnMessage={item.senderId === currentUserId}
            />
          )}
          contentContainerStyle={styles.messagesList}
          onStartReached={() => {
            if (hasMore) loadMore();
          }}
          ListHeaderComponent={
            isLoading ? (
              <LoadingSpinner message="Loading messages..." />
            ) : hasMore ? (
              <TouchableOpacity onPress={loadMore} style={styles.loadMoreBtn}>
                <Text style={styles.loadMoreText}>Load earlier messages</Text>
              </TouchableOpacity>
            ) : null
          }
          ListEmptyComponent={
            !isLoading ? (
              <View style={styles.emptyChat}>
                <Text style={styles.emptyChatText}>
                  No messages yet. Start the conversation!
                </Text>
              </View>
            ) : null
          }
        />

        {/* Input */}
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            value={inputText}
            onChangeText={setInputText}
            placeholder="Type a message..."
            placeholderTextColor={colors.neutral[400]}
            multiline
            maxLength={1000}
            editable={isConnected}
          />
          <TouchableOpacity
            style={[
              styles.sendButton,
              (!inputText.trim() || isSending || !isConnected) && styles.sendButtonDisabled,
            ]}
            onPress={handleSend}
            disabled={!inputText.trim() || isSending || !isConnected}
          >
            <Text style={styles.sendButtonText}>Send</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  closeText: { ...typography.label, color: colors.primary.gold },
  headerCenter: { alignItems: 'center', flex: 1 },
  headerTitle: { ...typography.h4, color: colors.foreground },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  onlineDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success },
  statusText: { ...typography.caption, color: colors.success },
  statusTextOffline: { ...typography.caption, color: colors.neutral[400] },
  errorBanner: {
    backgroundColor: colors.destructiveLight,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  errorText: { ...typography.bodySmall, color: colors.destructive },
  chatArea: { flex: 1 },
  messagesList: { padding: 16, flexGrow: 1 },
  messageRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, marginBottom: 12 },
  messageRowOwn: { justifyContent: 'flex-end' },
  messageBubble: {
    maxWidth: '75%',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 16,
  },
  messageBubbleOwn: {
    backgroundColor: colors.primary.gold,
    borderBottomRightRadius: 4,
  },
  messageBubbleOther: {
    backgroundColor: colors.neutral[100],
    borderBottomLeftRadius: 4,
  },
  messageBubbleStaff: {
    backgroundColor: colors.infoLight,
  },
  senderRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 2 },
  senderName: { ...typography.caption, color: colors.neutral[600], fontWeight: '600' },
  staffBadge: {
    backgroundColor: colors.info,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  staffBadgeText: { ...typography.caption, color: '#fff', fontSize: 10 },
  messageText: { ...typography.body, color: colors.foreground },
  messageTextOwn: { color: colors.primary.navy },
  messageTime: { ...typography.caption, color: colors.neutral[400], marginTop: 4, textAlign: 'right' },
  messageTimeOwn: { color: colors.primary.navyLight },
  loadMoreBtn: { alignItems: 'center', paddingVertical: 8 },
  loadMoreText: { ...typography.bodySmall, color: colors.primary.gold },
  emptyChat: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 60 },
  emptyChatText: { ...typography.body, color: colors.neutral[400], textAlign: 'center' },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 8,
  },
  input: {
    flex: 1,
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[100],
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: colors.primary.gold,
    borderRadius: 20,
    paddingHorizontal: 18,
    paddingVertical: 10,
  },
  sendButtonDisabled: { opacity: 0.4 },
  sendButtonText: { ...typography.label, color: colors.primary.navy, fontWeight: '700' },
});
