// Full-screen achievement unlock celebration modal with animations

import React, { useEffect, useMemo } from 'react';
import { View, Text, StyleSheet, Modal, TouchableOpacity, Dimensions } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withSequence,
  withDelay,
  withTiming,
  Easing,
  withRepeat,
} from 'react-native-reanimated';
import { colors, typography, spacing } from '@/theme';
import type { Achievement } from '@/types/gamification';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

interface AchievementUnlockModalProps {
  achievement: Achievement | null;
  onDismiss: () => void;
}

function Sparkle({ delay, x, y }: { delay: number; x: number; y: number }) {
  const opacity = useSharedValue(0);
  const scale = useSharedValue(0);
  const rotation = useSharedValue(0);

  useEffect(() => {
    opacity.value = withDelay(
      delay,
      withSequence(
        withTiming(1, { duration: 300 }),
        withDelay(1500, withTiming(0, { duration: 500 }))
      )
    );
    scale.value = withDelay(
      delay,
      withSequence(
        withSpring(1.2, { damping: 8 }),
        withTiming(0.8, { duration: 800 })
      )
    );
    rotation.value = withDelay(
      delay,
      withRepeat(withTiming(360, { duration: 2000, easing: Easing.linear }), -1)
    );
  }, [delay, opacity, scale, rotation]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [
      { scale: scale.value },
      { rotate: `${rotation.value}deg` },
    ],
  }));

  return (
    <Animated.View style={[styles.sparkle, { left: x, top: y }, animatedStyle]}>
      <Text style={styles.sparkleText}>✨</Text>
    </Animated.View>
  );
}

export function AchievementUnlockModal({ achievement, onDismiss }: AchievementUnlockModalProps) {
  const cardScale = useSharedValue(0);
  const cardOpacity = useSharedValue(0);
  const iconScale = useSharedValue(0);
  const backdropOpacity = useSharedValue(0);

  useEffect(() => {
    if (achievement) {
      backdropOpacity.value = withTiming(1, { duration: 300 });
      cardScale.value = withDelay(200, withSpring(1, { damping: 12, stiffness: 100 }));
      cardOpacity.value = withDelay(200, withTiming(1, { duration: 300 }));
      iconScale.value = withDelay(500, withSpring(1, { damping: 8, stiffness: 120 }));

      // Auto-dismiss after 5 seconds
      const timer = setTimeout(onDismiss, 5000);
      return () => clearTimeout(timer);
    } else {
      cardScale.value = 0;
      cardOpacity.value = 0;
      iconScale.value = 0;
      backdropOpacity.value = 0;
    }
  }, [achievement, cardScale, cardOpacity, iconScale, backdropOpacity, onDismiss]);

  const backdropStyle = useAnimatedStyle(() => ({
    opacity: backdropOpacity.value,
  }));

  const cardStyle = useAnimatedStyle(() => ({
    transform: [{ scale: cardScale.value }],
    opacity: cardOpacity.value,
  }));

  const iconStyle = useAnimatedStyle(() => ({
    transform: [{ scale: iconScale.value }],
  }));

  // Stabilize sparkle positions — only recompute when a new achievement appears
  const sparkles = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: i,
        delay: 300 + i * 100,
        x: Math.random() * (SCREEN_WIDTH - 40),
        y: 100 + Math.random() * 300,
      })),
    [achievement?.badgeName]
  );

  if (!achievement) return null;

  return (
    <Modal transparent animationType="none" visible={!!achievement} onRequestClose={onDismiss}>
      <Animated.View style={[styles.backdrop, backdropStyle]}>
        {sparkles.map((s) => (
          <Sparkle key={s.id} delay={s.delay} x={s.x} y={s.y} />
        ))}

        <Animated.View style={[styles.card, cardStyle]}>
          <View style={styles.headerStripe} />

          <Text style={styles.headerText}>Achievement Unlocked!</Text>

          <Animated.View style={[styles.iconCircle, iconStyle]}>
            <Text style={styles.achievementIcon}>{achievement.icon || '🏆'}</Text>
          </Animated.View>

          <Text style={styles.badgeName}>{achievement.badgeName}</Text>
          <Text style={styles.description}>{achievement.description}</Text>

          {achievement.category && (
            <Text style={styles.category}>{achievement.category}</Text>
          )}

          <TouchableOpacity style={styles.button} onPress={onDismiss} activeOpacity={0.8}>
            <Text style={styles.buttonText}>Awesome!</Text>
          </TouchableOpacity>
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  sparkle: {
    position: 'absolute',
    zIndex: 10,
  },
  sparkleText: {
    fontSize: 20,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: spacing.xl,
    alignItems: 'center',
    width: '100%',
    maxWidth: 320,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 10,
    overflow: 'hidden',
  },
  headerStripe: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 4,
    backgroundColor: colors.primary.gold,
  },
  headerText: {
    ...typography.caption,
    color: colors.primary.gold,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.primary.gold + '20',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.primary.gold,
    marginBottom: spacing.base,
  },
  achievementIcon: {
    fontSize: 40,
  },
  badgeName: {
    ...typography.h3,
    color: colors.foreground,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  description: {
    ...typography.bodySmall,
    color: colors.neutral[500],
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  category: {
    ...typography.caption,
    color: colors.neutral[400],
    marginBottom: spacing.lg,
  },
  button: {
    backgroundColor: colors.primary.gold,
    paddingHorizontal: spacing['2xl'],
    paddingVertical: spacing.md,
    borderRadius: 12,
    width: '100%',
    alignItems: 'center',
  },
  buttonText: {
    ...typography.button,
    color: colors.primary.navy,
    fontWeight: '700',
  },
});
