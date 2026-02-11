// Floating emoji reactions that animate upward and fade out
// Uses react-native-reanimated for smooth 60fps animations

import React, { useEffect, useRef } from 'react';
import { StyleSheet, Dimensions } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withDelay,
  Easing,
  runOnJS,
} from 'react-native-reanimated';
import type { FloatingEmoji } from '@/hooks/useSessionReactions';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

interface FloatingEmojiItemProps {
  item: FloatingEmoji;
  onFinished: (id: string) => void;
}

function FloatingEmojiItem({ item, onFinished }: FloatingEmojiItemProps) {
  const translateY = useSharedValue(0);
  const opacity = useSharedValue(0);
  const scale = useSharedValue(0.5);
  const rotate = useSharedValue(0);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  useEffect(() => {
    const drift = -20 + Math.random() * 40;
    const duration = 3000 + Math.random() * 1000;
    const itemId = item.id;

    const handleFinished = (id: string) => {
      onFinishedRef.current(id);
    };

    opacity.value = withTiming(1, { duration: 200 });
    scale.value = withTiming(0.8 + Math.random() * 0.4, { duration: 300 });
    translateY.value = withTiming(-(SCREEN_HEIGHT * 0.5), {
      duration,
      easing: Easing.out(Easing.cubic),
    });
    rotate.value = withTiming(drift, { duration });

    // Fade out at the end
    opacity.value = withDelay(
      duration - 600,
      withTiming(0, { duration: 600 }, (finished) => {
        if (finished) {
          runOnJS(handleFinished)(itemId);
        }
      }),
    );
  }, []);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateY: translateY.value },
      { rotate: `${rotate.value}deg` },
      { scale: scale.value },
    ],
    opacity: opacity.value,
  }));

  return (
    <Animated.Text
      style={[
        styles.emoji,
        { left: `${item.x}%` },
        animatedStyle,
      ]}
    >
      {item.emoji}
    </Animated.Text>
  );
}

interface FloatingReactionsProps {
  emojis: FloatingEmoji[];
  onEmojiFinished?: (id: string) => void;
}

export function FloatingReactions({ emojis, onEmojiFinished }: FloatingReactionsProps) {
  const handleFinished = (id: string) => {
    onEmojiFinished?.(id);
  };

  if (emojis.length === 0) return null;

  return (
    <Animated.View style={styles.container} pointerEvents="none">
      {emojis.map((item) => (
        <FloatingEmojiItem key={item.id} item={item} onFinished={handleFinished} />
      ))}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    overflow: 'hidden',
  },
  emoji: {
    position: 'absolute',
    bottom: 80,
    fontSize: 28,
  },
});
