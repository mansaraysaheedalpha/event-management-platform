import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
  PanResponder,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, typography, spacing } from '@/theme';
import type { ToastMessage } from '@/types/notifications';

const SCREEN_WIDTH = Dimensions.get('window').width;

const TYPE_STYLES = {
  success: { bg: colors.success, icon: '✓' },
  error: { bg: colors.destructive, icon: '✕' },
  warning: { bg: colors.warning, icon: '!' },
  info: { bg: colors.info, icon: 'i' },
} as const;

interface ToastBannerProps {
  toast: ToastMessage;
  onDismiss: (id: string) => void;
  onPress?: (actionUrl?: string) => void;
}

export function ToastBanner({ toast, onDismiss, onPress }: ToastBannerProps) {
  const insets = useSafeAreaInsets();
  const translateY = useRef(new Animated.Value(-100)).current;
  const translateX = useRef(new Animated.Value(0)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, gestureState) =>
        Math.abs(gestureState.dx) > 10 || Math.abs(gestureState.dy) > 10,
      onPanResponderMove: (_, gestureState) => {
        // Swipe up to dismiss
        if (gestureState.dy < 0) {
          translateY.setValue(gestureState.dy);
        }
        // Swipe left/right to dismiss
        if (Math.abs(gestureState.dx) > 10) {
          translateX.setValue(gestureState.dx);
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        if (gestureState.dy < -50 || Math.abs(gestureState.dx) > SCREEN_WIDTH * 0.3) {
          dismiss();
        } else {
          Animated.parallel([
            Animated.spring(translateY, { toValue: 0, useNativeDriver: true }),
            Animated.spring(translateX, { toValue: 0, useNativeDriver: true }),
          ]).start();
        }
      },
    }),
  ).current;

  const dismiss = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    Animated.parallel([
      Animated.timing(translateY, { toValue: -100, duration: 200, useNativeDriver: true }),
      Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => onDismiss(toast.id));
  };

  useEffect(() => {
    // Slide in
    Animated.parallel([
      Animated.spring(translateY, { toValue: 0, useNativeDriver: true, damping: 15 }),
      Animated.timing(opacity, { toValue: 1, duration: 300, useNativeDriver: true }),
    ]).start();

    // Auto-dismiss
    const duration = toast.duration ?? 4000;
    timerRef.current = setTimeout(dismiss, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const style = TYPE_STYLES[toast.type];

  return (
    <Animated.View
      style={[
        styles.container,
        { top: insets.top + spacing.xs },
        { transform: [{ translateY }, { translateX }], opacity },
      ]}
      {...panResponder.panHandlers}
    >
      <TouchableOpacity
        style={styles.inner}
        activeOpacity={0.9}
        onPress={() => {
          if (onPress) onPress(toast.actionUrl);
          dismiss();
        }}
      >
        <View style={[styles.iconContainer, { backgroundColor: style.bg }]}>
          <Text style={styles.iconText}>{style.icon}</Text>
        </View>
        <View style={styles.textContainer}>
          <Text style={styles.title} numberOfLines={1}>
            {toast.title}
          </Text>
          {toast.message ? (
            <Text style={styles.message} numberOfLines={2}>
              {toast.message}
            </Text>
          ) : null}
        </View>
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    zIndex: 9999,
  },
  inner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 8,
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  iconText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  textContainer: {
    flex: 1,
  },
  title: {
    ...typography.label,
    color: colors.foreground,
  },
  message: {
    ...typography.caption,
    color: colors.neutral[500],
    marginTop: 2,
  },
});
