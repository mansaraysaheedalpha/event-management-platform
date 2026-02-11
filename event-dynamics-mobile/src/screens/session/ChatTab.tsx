import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { Avatar } from '@/components/ui';
import { colors, typography } from '@/theme';
import { useSessionChat, ChatMessage } from '@/hooks/useSessionChat';

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

interface MessageBubbleProps {
  message: ChatMessage;
  isOwn: boolean;
}

const MessageBubble = React.memo(function MessageBubble({ message, isOwn }: MessageBubbleProps) {
  const authorName = `${message.author.firstName} ${message.author.lastName}`.trim();

  return (
    <View style={[styles.bubbleRow, isOwn && styles.bubbleRowOwn]}>
      {!isOwn && (
        <Avatar name={authorName} size={32} />
      )}
      <View style={[styles.bubble, isOwn ? styles.bubbleOwn : styles.bubbleOther]}>
        {!isOwn && (
          <Text style={styles.bubbleAuthor}>{authorName}</Text>
        )}
        {message.parentMessage && (
          <View style={styles.replyPreview}>
            <Text style={styles.replyAuthor} numberOfLines={1}>
              {message.parentMessage.author.firstName}
            </Text>
            <Text style={styles.replyText} numberOfLines={1}>
              {message.parentMessage.text}
            </Text>
          </View>
        )}
        <Text style={[styles.bubbleText, isOwn && styles.bubbleTextOwn]}>
          {message.text}
        </Text>
        <Text style={[styles.bubbleTime, isOwn && styles.bubbleTimeOwn]}>
          {formatTime(message.timestamp)}
          {message.isEdited && ' (edited)'}
        </Text>
      </View>
    </View>
  );
});

export function ChatTab() {
  const {
    messages,
    isJoined,
    chatOpen,
    isSending,
    error,
    currentUserId,
    sendMessage,
    clearError,
  } = useSessionChat();

  const [text, setText] = useState('');
  const flatListRef = useRef<FlashList<ChatMessage>>(null);

  const handleSend = useCallback(async () => {
    if (!text.trim()) return;
    const msg = text;
    setText('');
    await sendMessage(msg);
  }, [text, sendMessage]);

  const renderItem = useCallback(
    ({ item }: { item: ChatMessage }) => (
      <MessageBubble message={item} isOwn={item.authorId === currentUserId} />
    ),
    [currentUserId],
  );

  const keyExtractor = useCallback((item: ChatMessage) => item.id, []);

  if (!isJoined) {
    return (
      <View style={styles.center}>
        <Text style={styles.statusText}>Connecting to chat...</Text>
      </View>
    );
  }

  if (!chatOpen) {
    return (
      <View style={styles.center}>
        <Text style={styles.disabledIcon}>💬</Text>
        <Text style={styles.statusText}>Chat is currently closed</Text>
        <Text style={styles.subText}>The organizer has disabled chat for this session</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={140}
    >
      {error && (
        <TouchableOpacity style={styles.errorBanner} onPress={clearError}>
          <Text style={styles.errorText}>{error}</Text>
        </TouchableOpacity>
      )}

      <FlashList
        ref={flatListRef}
        data={messages}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        inverted
        estimatedItemSize={80}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No messages yet</Text>
            <Text style={styles.emptySubText}>Be the first to say something!</Text>
          </View>
        }
      />

      <View style={styles.inputRow}>
        <TextInput
          style={styles.textInput}
          value={text}
          onChangeText={setText}
          placeholder="Type a message..."
          placeholderTextColor={colors.neutral[400]}
          maxLength={1000}
          multiline
          editable={!isSending}
          accessibilityLabel="Type a message"
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!text.trim() || isSending) && styles.sendBtnDisabled]}
          onPress={handleSend}
          disabled={!text.trim() || isSending}
          accessibilityRole="button"
          accessibilityLabel="Send message"
        >
          <Text style={styles.sendBtnText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  statusText: { ...typography.body, color: colors.neutral[500], marginTop: 8 },
  subText: { ...typography.bodySmall, color: colors.neutral[400], marginTop: 4, textAlign: 'center' },
  disabledIcon: { fontSize: 40 },
  errorBanner: {
    backgroundColor: colors.destructiveLight,
    padding: 10,
    alignItems: 'center',
  },
  errorText: { ...typography.bodySmall, color: colors.destructive },
  listContent: { paddingHorizontal: 12, paddingTop: 8 },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 60,
    // Inverted FlatList flips everything — rotate to un-flip empty state
    transform: [{ scaleY: -1 }],
  },
  emptyText: { ...typography.body, color: colors.neutral[500] },
  emptySubText: { ...typography.bodySmall, color: colors.neutral[400], marginTop: 4 },
  bubbleRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginBottom: 8,
    gap: 8,
  },
  bubbleRowOwn: {
    flexDirection: 'row-reverse',
  },
  bubble: {
    maxWidth: '75%',
    borderRadius: 16,
    padding: 10,
    paddingBottom: 6,
  },
  bubbleOwn: {
    backgroundColor: colors.primary.navy,
    borderBottomRightRadius: 4,
  },
  bubbleOther: {
    backgroundColor: colors.neutral[100],
    borderBottomLeftRadius: 4,
  },
  bubbleAuthor: {
    ...typography.caption,
    fontWeight: '600',
    color: colors.primary.navy,
    marginBottom: 2,
  },
  bubbleText: {
    ...typography.body,
    color: colors.foreground,
  },
  bubbleTextOwn: {
    color: '#FFFFFF',
  },
  bubbleTime: {
    ...typography.caption,
    color: colors.neutral[400],
    marginTop: 2,
    alignSelf: 'flex-end',
    fontSize: 10,
  },
  bubbleTimeOwn: {
    color: 'rgba(255,255,255,0.6)',
  },
  replyPreview: {
    borderLeftWidth: 2,
    borderLeftColor: colors.primary.gold,
    paddingLeft: 8,
    marginBottom: 4,
  },
  replyAuthor: {
    ...typography.caption,
    fontWeight: '600',
    color: colors.primary.gold,
  },
  replyText: {
    ...typography.caption,
    color: colors.neutral[400],
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.card,
    gap: 8,
  },
  textInput: {
    flex: 1,
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[100],
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxHeight: 100,
  },
  sendBtn: {
    backgroundColor: colors.primary.gold,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  sendBtnText: {
    ...typography.label,
    color: colors.primary.navy,
    fontWeight: '700',
  },
});
