import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNetwork } from '@/context/NetworkContext';
import { colors, typography } from '@/theme';

export function OfflineBanner() {
  const { isConnected } = useNetwork();
  const insets = useSafeAreaInsets();
  const translateY = useSharedValue(-80);
  const [visible, setVisible] = useState(false);
  const [showReconnected, setShowReconnected] = useState(false);
  const wasOffline = useRef(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (!isConnected) {
      wasOffline.current = true;
      setShowReconnected(false);
      setVisible(true);
      translateY.value = withTiming(0, {
        duration: 200,
        easing: Easing.out(Easing.ease),
      });
    } else if (wasOffline.current) {
      wasOffline.current = false;
      setShowReconnected(true);

      reconnectTimer.current = setTimeout(() => {
        translateY.value = withTiming(-80, {
          duration: 200,
          easing: Easing.in(Easing.ease),
        });
        setTimeout(() => {
          setVisible(false);
          setShowReconnected(false);
        }, 250);
      }, 2000);
    } else {
      setVisible(false);
    }

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [isConnected, translateY]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
  }));

  if (!visible) return null;

  const bgColor = showReconnected ? colors.success : colors.neutral[900];
  const message = showReconnected
    ? 'Back online'
    : 'No internet connection';

  return (
    <Animated.View
      style={[
        styles.container,
        { paddingTop: insets.top + 4, backgroundColor: bgColor },
        animatedStyle,
      ]}
      accessibilityRole="alert"
      accessibilityLabel={message}
    >
      <View style={styles.content}>
        <Text style={styles.icon}>
          {showReconnected ? '\u2705' : '\uD83D\uDCF6'}
        </Text>
        <Text style={styles.text}>{message}</Text>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 9999,
    paddingBottom: 8,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  icon: {
    fontSize: 14,
  },
  text: {
    ...typography.bodySmall,
    color: '#FFFFFF',
    fontWeight: '600',
  },
});
