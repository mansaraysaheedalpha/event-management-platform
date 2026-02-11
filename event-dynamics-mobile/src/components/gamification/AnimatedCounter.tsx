// Animated score counter with spring animation using react-native-reanimated

import React, { useEffect } from 'react';
import { StyleSheet, TextStyle, StyleProp } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withSpring,
  useDerivedValue,
} from 'react-native-reanimated';
import { colors, typography } from '@/theme';

const AnimatedText = Animated.createAnimatedComponent(
  require('react-native').TextInput
);

interface AnimatedCounterProps {
  value: number;
  style?: StyleProp<TextStyle>;
  prefix?: string;
  suffix?: string;
}

export function AnimatedCounter({
  value,
  style,
  prefix = '',
  suffix = '',
}: AnimatedCounterProps) {
  const animatedValue = useSharedValue(0);

  useEffect(() => {
    animatedValue.value = withSpring(value, {
      damping: 20,
      stiffness: 90,
      mass: 1,
    });
  }, [value, animatedValue]);

  const displayValue = useDerivedValue(() => {
    return `${prefix}${Math.round(animatedValue.value).toLocaleString()}${suffix}`;
  });

  const animatedProps = useAnimatedProps(() => {
    return {
      text: displayValue.value,
      defaultValue: displayValue.value,
    } as Record<string, string>;
  });

  return (
    <AnimatedText
      animatedProps={animatedProps}
      editable={false}
      style={[styles.counter, style]}
      underlineColorAndroid="transparent"
    />
  );
}

const styles = StyleSheet.create({
  counter: {
    ...typography.h1,
    color: colors.primary.navy,
    fontWeight: '700',
    padding: 0,
    margin: 0,
  },
});
