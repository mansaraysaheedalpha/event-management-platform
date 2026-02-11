// Ported from ../globalconnect/src/hooks/use-session-reactions.ts
// Mobile-adapted: uses shared socket, expo-haptics, react-native-reanimated ready

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSessionSocket } from '@/context/SessionSocketContext';
import * as Haptics from 'expo-haptics';

export const ALLOWED_EMOJIS = [
  '👍', '❤️', '🎉', '💡', '😂', '👏',
  '🔥', '🙏', '🤝', '🚀', '🙌', '✅',
  '🎶', '🕺', '📢', '📸', '🌍', '🧠',
] as const;

export type AllowedEmoji = (typeof ALLOWED_EMOJIS)[number];

export interface FloatingEmoji {
  id: string;
  emoji: string;
  x: number; // 0-100 percentage
  createdAt: number;
}

export interface ReactionBurst {
  counts: Record<string, number>;
  timestamp: number;
}

const RATE_LIMIT = {
  maxPerSecond: 3,
  burstLimit: 10,
  burstWindow: 5000,
};

const POPULAR_EMOJIS: string[] = Array.from(ALLOWED_EMOJIS.slice(0, 6));

export function useSessionReactions() {
  const { socket, isJoined, reactionsOpen } = useSessionSocket();

  const [floatingEmojis, setFloatingEmojis] = useState<FloatingEmoji[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [totalSent, setTotalSent] = useState(0);

  // Rate limiting
  const reactionTimestamps = useRef<number[]>([]);
  const burstCount = useRef(0);
  const burstWindowStart = useRef(Date.now());
  const emojiIdCounter = useRef(0);

  const canSendReaction = useCallback((): boolean => {
    const now = Date.now();
    if (now - burstWindowStart.current > RATE_LIMIT.burstWindow) {
      burstCount.current = 0;
      burstWindowStart.current = now;
    }
    if (burstCount.current >= RATE_LIMIT.burstLimit) return false;

    const oneSecondAgo = now - 1000;
    reactionTimestamps.current = reactionTimestamps.current.filter((t) => t > oneSecondAgo);
    return reactionTimestamps.current.length < RATE_LIMIT.maxPerSecond;
  }, []);

  const recordReaction = useCallback(() => {
    reactionTimestamps.current.push(Date.now());
    burstCount.current++;
  }, []);

  const addFloatingEmoji = useCallback((emoji: string, count: number = 1) => {
    const newEmojis: FloatingEmoji[] = [];
    const maxToAdd = Math.min(count, 10);
    for (let i = 0; i < maxToAdd; i++) {
      emojiIdCounter.current++;
      newEmojis.push({
        id: `emoji-${emojiIdCounter.current}-${Date.now()}`,
        emoji,
        x: 10 + Math.random() * 80,
        createdAt: Date.now() + i * 100,
      });
    }
    setFloatingEmojis((prev) => [...prev, ...newEmojis].slice(-50));
  }, []);

  // Cleanup expired floating emojis every second
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      setFloatingEmojis((prev) => prev.filter((e) => now - e.createdAt < 4000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Socket listeners
  useEffect(() => {
    if (!socket) return;

    const handleBurst = (counts: Record<string, number>) => {
      Object.entries(counts).forEach(([emoji, count]) => {
        addFloatingEmoji(emoji, count);
      });
    };

    socket.on('reaction.burst', handleBurst);

    return () => {
      socket.off('reaction.burst', handleBurst);
    };
  }, [socket, addFloatingEmoji]);

  const sendReaction = useCallback(
    (emoji: string): boolean => {
      if (!socket || !isJoined) return false;
      if (!ALLOWED_EMOJIS.includes(emoji as AllowedEmoji)) return false;

      if (!canSendReaction()) {
        setError('Slow down! Too many reactions.');
        return false;
      }

      socket.emit('reaction.send', { emoji });
      recordReaction();
      addFloatingEmoji(emoji, 1);
      setTotalSent((prev) => prev + 1);
      setError(null);

      // Haptic feedback
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});

      return true;
    },
    [socket, isJoined, canSendReaction, recordReaction, addFloatingEmoji],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    floatingEmojis,
    error,
    totalSent,
    reactionsOpen,
    isJoined,
    sendReaction,
    clearError,
    popularEmojis: POPULAR_EMOJIS,
    ALLOWED_EMOJIS,
  };
}
