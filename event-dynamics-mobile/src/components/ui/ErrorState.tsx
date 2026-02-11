import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Button } from './Button';
import { colors, typography, spacing } from '@/theme';

type ErrorVariant = 'error' | 'network' | 'notFound' | 'unauthorized' | 'serverError';

interface ErrorStateProps {
  title: string;
  description?: string;
  variant?: ErrorVariant;
  onRetry?: () => void;
  onGoBack?: () => void;
  retryLabel?: string;
}

const variantConfig: Record<
  ErrorVariant,
  { icon: string; iconColor: string; bgColor: string }
> = {
  error: {
    icon: '\u26A0',
    iconColor: colors.destructive,
    bgColor: colors.destructiveLight,
  },
  network: {
    icon: '\uD83D\uDCF6',
    iconColor: colors.warning,
    bgColor: colors.warningLight,
  },
  notFound: {
    icon: '\uD83D\uDD0D',
    iconColor: colors.info,
    bgColor: colors.infoLight,
  },
  unauthorized: {
    icon: '\uD83D\uDD12',
    iconColor: colors.warning,
    bgColor: colors.warningLight,
  },
  serverError: {
    icon: '\uD83D\uDDA5',
    iconColor: colors.destructive,
    bgColor: colors.destructiveLight,
  },
};

export function ErrorState({
  title,
  description,
  variant = 'error',
  onRetry,
  onGoBack,
  retryLabel = 'Try again',
}: ErrorStateProps) {
  const config = variantConfig[variant];

  return (
    <View style={styles.container}>
      <View style={[styles.iconCircle, { backgroundColor: config.bgColor }]}>
        <Text style={styles.icon}>{config.icon}</Text>
      </View>
      <Text style={styles.title}>{title}</Text>
      {description && <Text style={styles.description}>{description}</Text>}
      <View style={styles.actions}>
        {onRetry && (
          <Button title={retryLabel} onPress={onRetry} variant="primary" />
        )}
        {onGoBack && (
          <Button title="Go back" onPress={onGoBack} variant="outline" />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing['2xl'],
    backgroundColor: colors.background,
  },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  icon: {
    fontSize: 32,
  },
  title: {
    ...typography.h3,
    color: colors.foreground,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  description: {
    ...typography.body,
    color: colors.neutral[500],
    textAlign: 'center',
    marginBottom: spacing.xl,
    maxWidth: 300,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
});
