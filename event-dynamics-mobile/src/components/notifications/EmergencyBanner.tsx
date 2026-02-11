import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, typography, spacing } from '@/theme';
import type { EmergencyAlert, NotificationSeverity } from '@/types/notifications';

const SEVERITY_STYLES: Record<NotificationSeverity, { bg: string; text: string }> = {
  critical: { bg: colors.destructive, text: '#FFFFFF' },
  high: { bg: '#F97316', text: '#FFFFFF' },
  medium: { bg: colors.warning, text: '#000000' },
  low: { bg: colors.info, text: '#FFFFFF' },
};

const AUTO_DISMISS_MS = 15000; // 15s for non-critical

interface EmergencyBannerProps {
  alert: EmergencyAlert;
  onDismiss: () => void;
}

export function EmergencyBanner({ alert, onDismiss }: EmergencyBannerProps) {
  const insets = useSafeAreaInsets();
  const slideAnim = useRef(new Animated.Value(-200)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // Slide in
    Animated.spring(slideAnim, {
      toValue: 0,
      useNativeDriver: true,
      damping: 12,
    }).start();

    // Pulse for critical severity
    if (alert.severity === 'critical') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 0.85, duration: 500, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 500, useNativeDriver: true }),
        ]),
      ).start();
    }

    // Auto-dismiss non-critical
    if (alert.severity !== 'critical') {
      const timer = setTimeout(() => {
        Animated.timing(slideAnim, {
          toValue: -200,
          duration: 300,
          useNativeDriver: true,
        }).start(onDismiss);
      }, AUTO_DISMISS_MS);
      return () => clearTimeout(timer);
    }

    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const style = SEVERITY_STYLES[alert.severity];

  return (
    <Animated.View
      style={[
        styles.container,
        {
          backgroundColor: style.bg,
          paddingTop: insets.top + spacing.sm,
          transform: [{ translateY: slideAnim }],
          opacity: pulseAnim,
        },
      ]}
    >
      <View style={styles.content}>
        <Text style={styles.icon}>
          {alert.severity === 'critical' ? '🚨' : '⚠️'}
        </Text>
        <View style={styles.textContainer}>
          <Text style={[styles.alertType, { color: style.text }]}>
            {alert.alertType} ALERT
          </Text>
          <Text style={[styles.message, { color: style.text }]} numberOfLines={3}>
            {alert.message}
          </Text>
        </View>
        <TouchableOpacity onPress={onDismiss} style={styles.dismissButton}>
          <Text style={[styles.dismissText, { color: style.text }]}>✕</Text>
        </TouchableOpacity>
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
    zIndex: 10000,
    paddingBottom: spacing.md,
    paddingHorizontal: spacing.base,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  icon: {
    fontSize: 24,
    marginRight: spacing.md,
  },
  textContainer: {
    flex: 1,
  },
  alertType: {
    ...typography.label,
    fontWeight: '800',
    letterSpacing: 1,
    marginBottom: 2,
  },
  message: {
    ...typography.bodySmall,
    fontWeight: '500',
  },
  dismissButton: {
    padding: spacing.sm,
    marginLeft: spacing.sm,
  },
  dismissText: {
    fontSize: 18,
    fontWeight: '700',
  },
});
