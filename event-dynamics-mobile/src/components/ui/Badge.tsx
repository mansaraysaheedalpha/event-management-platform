import React from 'react';
import { View, Text, StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { colors, typography } from '@/theme';

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'info';

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  style?: StyleProp<ViewStyle>;
}

const variantColors: Record<BadgeVariant, { bg: string; text: string }> = {
  default: { bg: colors.neutral[100], text: colors.neutral[700] },
  success: { bg: colors.successLight, text: colors.success },
  warning: { bg: colors.warningLight, text: '#92400E' },
  destructive: { bg: colors.destructiveLight, text: colors.destructive },
  info: { bg: colors.infoLight, text: colors.info },
};

export function Badge({ label, variant = 'default', style }: BadgeProps) {
  const color = variantColors[variant];
  return (
    <View
      style={[styles.badge, { backgroundColor: color.bg }, style]}
      accessibilityRole="text"
      accessibilityLabel={label}
    >
      <Text style={[styles.text, { color: color.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 9999,
    alignSelf: 'flex-start',
  },
  text: {
    ...typography.caption,
    fontWeight: '600',
  },
});
