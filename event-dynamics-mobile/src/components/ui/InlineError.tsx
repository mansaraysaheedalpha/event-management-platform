import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { colors, typography, spacing } from '@/theme';

interface InlineErrorProps {
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export function InlineError({ message, onRetry, onDismiss }: InlineErrorProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>{'\u26A0'}</Text>
      <Text style={styles.message} numberOfLines={2}>
        {message}
      </Text>
      {onRetry && (
        <TouchableOpacity
          style={styles.action}
          onPress={onRetry}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel="Retry"
        >
          <Text style={styles.actionText}>Retry</Text>
        </TouchableOpacity>
      )}
      {onDismiss && (
        <TouchableOpacity
          style={styles.action}
          onPress={onDismiss}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel="Dismiss error"
        >
          <Text style={styles.dismissText}>{'\u2715'}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.destructiveLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 8,
    gap: spacing.sm,
  },
  icon: {
    fontSize: 16,
  },
  message: {
    ...typography.bodySmall,
    color: colors.destructive,
    flex: 1,
  },
  action: {
    minWidth: 44,
    minHeight: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionText: {
    ...typography.label,
    color: colors.destructive,
    fontWeight: '700',
  },
  dismissText: {
    fontSize: 16,
    color: colors.destructive,
  },
});
