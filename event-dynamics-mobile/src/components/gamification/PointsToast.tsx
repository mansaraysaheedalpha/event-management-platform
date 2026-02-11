// Floating "+X pts" toast when points are earned

import React, { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSequence,
  withDelay,
  Easing,
} from 'react-native-reanimated';
import { colors, typography } from '@/theme';
import type { RecentPointEvent } from '@/types/gamification';
import { REASON_EMOJI } from '@/types/gamification';

interface PointsToastProps {
  events: RecentPointEvent[];
}

function SinglePointToast({ event }: { event: RecentPointEvent }) {
  const translateY = useSharedValue(20);
  const opacity = useSharedValue(0);
  const scale = useSharedValue(0.8);

  useEffect(() => {
    translateY.value = withSequence(
      withTiming(-10, { duration: 300, easing: Easing.out(Easing.cubic) }),
      withDelay(3000, withTiming(-60, { duration: 1000 }))
    );
    opacity.value = withSequence(
      withTiming(1, { duration: 200 }),
      withDelay(3200, withTiming(0, { duration: 800 }))
    );
    scale.value = withSequence(
      withTiming(1.1, { duration: 200, easing: Easing.out(Easing.cubic) }),
      withTiming(1, { duration: 150 })
    );
  }, [translateY, opacity, scale]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }, { scale: scale.value }],
    opacity: opacity.value,
  }));

  const emoji = REASON_EMOJI[event.reason] || '🎯';
  const hasMultiplier = event.streakMultiplier && event.streakMultiplier > 1;

  return (
    <Animated.View style={[styles.toast, animatedStyle]}>
      <Text style={styles.emoji}>{emoji}</Text>
      <Text style={styles.points}>+{event.points} pts</Text>
      {hasMultiplier && (
        <View style={styles.multiplierBadge}>
          <Text style={styles.multiplierText}>{event.streakMultiplier}x</Text>
        </View>
      )}
    </Animated.View>
  );
}

export function PointsToast({ events }: PointsToastProps) {
  if (events.length === 0) return null;

  return (
    <View style={styles.container} pointerEvents="none">
      {events.slice(-3).map((event) => (
        <SinglePointToast key={event.id} event={event} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 100,
    right: 16,
    zIndex: 50,
    gap: 8,
  },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary.gold,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  emoji: {
    fontSize: 16,
  },
  points: {
    ...typography.label,
    color: colors.primary.navy,
    fontWeight: '700',
  },
  multiplierBadge: {
    backgroundColor: colors.primary.navy,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 10,
    marginLeft: 2,
  },
  multiplierText: {
    ...typography.caption,
    color: colors.primary.gold,
    fontWeight: '700',
    fontSize: 10,
  },
});
