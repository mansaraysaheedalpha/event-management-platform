// Chat message bubble component
import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { colors, typography, spacing } from '@/theme';
import type { DirectMessage, MessageStatus } from '@/types/networking';

interface MessageBubbleProps {
  message: DirectMessage;
  isOwn: boolean;
  onRetry?: (messageId: string) => void;
  onLongPress?: (message: DirectMessage) => void;
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function StatusIcon({ status }: { status?: MessageStatus }) {
  switch (status) {
    case 'sending': return <Text style={styles.statusIcon}>{'⏳'}</Text>;
    case 'sent': return <Text style={styles.statusIcon}>{'✓'}</Text>;
    case 'delivered': return <Text style={styles.statusIcon}>{'✓✓'}</Text>;
    case 'read': return <Text style={[styles.statusIcon, styles.readIcon]}>{'✓✓'}</Text>;
    case 'failed': return <Text style={[styles.statusIcon, styles.failedIcon]}>{'!'}</Text>;
    default: return null;
  }
}

export function MessageBubble({ message, isOwn, onRetry, onLongPress }: MessageBubbleProps) {
  const isFailed = message.status === 'failed';

  return (
    <View style={[styles.wrapper, isOwn ? styles.wrapperOwn : styles.wrapperOther]}>
      <Pressable
        onLongPress={() => onLongPress?.(message)}
        style={[
          styles.bubble,
          isOwn ? styles.bubbleOwn : styles.bubbleOther,
          isFailed && styles.bubbleFailed,
        ]}
      >
        <Text style={[styles.text, isOwn ? styles.textOwn : styles.textOther]}>
          {message.text}
        </Text>
        <View style={styles.meta}>
          {message.isEdited && <Text style={[styles.edited, isOwn && styles.editedOwn]}>edited</Text>}
          <Text style={[styles.time, isOwn ? styles.timeOwn : styles.timeOther]}>
            {formatTime(message.timestamp)}
          </Text>
          {isOwn && <StatusIcon status={message.status} />}
        </View>
      </Pressable>
      {isFailed && (
        <Pressable onPress={() => onRetry?.(message.id)} style={styles.retryBtn}>
          <Text style={styles.retryText}>Tap to retry</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginVertical: 2,
    paddingHorizontal: spacing.base,
    maxWidth: '80%',
  },
  wrapperOwn: {
    alignSelf: 'flex-end',
  },
  wrapperOther: {
    alignSelf: 'flex-start',
  },
  bubble: {
    borderRadius: 16,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  bubbleOwn: {
    backgroundColor: colors.primary.navy,
    borderBottomRightRadius: 4,
  },
  bubbleOther: {
    backgroundColor: colors.neutral[100],
    borderBottomLeftRadius: 4,
  },
  bubbleFailed: {
    backgroundColor: colors.destructiveLight,
  },
  text: {
    ...typography.body,
  },
  textOwn: {
    color: '#FFFFFF',
  },
  textOther: {
    color: colors.foreground,
  },
  meta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 4,
    marginTop: 2,
  },
  time: {
    fontSize: 10,
  },
  timeOwn: {
    color: 'rgba(255,255,255,0.6)',
  },
  timeOther: {
    color: colors.neutral[400],
  },
  edited: {
    fontSize: 10,
    color: colors.neutral[400],
    fontStyle: 'italic',
  },
  editedOwn: {
    color: 'rgba(255,255,255,0.5)',
  },
  statusIcon: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.6)',
  },
  readIcon: {
    color: colors.primary.gold,
  },
  failedIcon: {
    color: colors.destructive,
    fontWeight: '700',
  },
  retryBtn: {
    alignSelf: 'flex-end',
    marginTop: 2,
  },
  retryText: {
    ...typography.caption,
    color: colors.destructive,
  },
});
