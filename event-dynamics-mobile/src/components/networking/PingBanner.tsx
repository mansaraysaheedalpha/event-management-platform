// Proximity ping notification banner
import React, { useEffect, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, Pressable, Animated } from 'react-native';
import { colors, typography, spacing } from '@/theme';
import type { ProximityPing } from '@/types/networking';

interface PingBannerProps {
  ping: ProximityPing;
  onDismiss: () => void;
  onReply?: (userId: string) => void;
  onStartChat?: (userId: string, userName: string) => void;
  autoDismissMs?: number;
}

export function PingBanner({ ping, onDismiss, onReply, onStartChat, autoDismissMs = 15000 }: PingBannerProps) {
  const slideAnim = useRef(new Animated.Value(-100)).current;

  useEffect(() => {
    Animated.spring(slideAnim, {
      toValue: 0,
      useNativeDriver: true,
      damping: 15,
    }).start();

    const timer = setTimeout(() => {
      Animated.timing(slideAnim, {
        toValue: -100,
        duration: 200,
        useNativeDriver: true,
      }).start(() => onDismiss());
    }, autoDismissMs);

    return () => clearTimeout(timer);
  }, [slideAnim, autoDismissMs, onDismiss]);

  const handleReply = useCallback(() => onReply?.(ping.fromUser.id), [ping.fromUser.id, onReply]);
  const handleChat = useCallback(() => onStartChat?.(ping.fromUser.id, ping.fromUser.name), [ping.fromUser, onStartChat]);

  return (
    <Animated.View style={[styles.container, { transform: [{ translateY: slideAnim }] }]}>
      <View style={styles.content}>
        <View style={styles.iconWrap}>
          <Text style={styles.icon}>{'📍'}</Text>
        </View>
        <View style={styles.info}>
          <Text style={styles.sender}>{ping.fromUser.name}</Text>
          <Text style={styles.message} numberOfLines={2}>{ping.message}</Text>
        </View>
        <Pressable onPress={onDismiss} style={styles.dismissBtn}>
          <Text style={styles.dismiss}>{'✕'}</Text>
        </Pressable>
      </View>
      <View style={styles.actions}>
        <Pressable style={styles.actionBtn} onPress={handleReply}>
          <Text style={styles.actionText}>Reply</Text>
        </Pressable>
        <Pressable style={[styles.actionBtn, styles.chatBtn]} onPress={handleChat}>
          <Text style={[styles.actionText, styles.chatText]}>Chat</Text>
        </Pressable>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.primary.navy,
    borderRadius: 12,
    marginHorizontal: spacing.base,
    marginBottom: spacing.sm,
    overflow: 'hidden',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    gap: spacing.sm,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    fontSize: 18,
  },
  info: {
    flex: 1,
  },
  sender: {
    ...typography.label,
    color: '#FFFFFF',
  },
  message: {
    ...typography.bodySmall,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  dismissBtn: {
    padding: spacing.xs,
  },
  dismiss: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.5)',
  },
  actions: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.1)',
  },
  actionBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  actionText: {
    ...typography.label,
    color: 'rgba(255,255,255,0.8)',
    fontSize: 13,
  },
  chatBtn: {
    backgroundColor: colors.primary.gold,
    borderBottomRightRadius: 12,
  },
  chatText: {
    color: colors.primary.navy,
  },
});
