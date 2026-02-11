import React from 'react';
import { View, StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { colors } from '@/theme';

interface SeparatorProps {
  style?: StyleProp<ViewStyle>;
  vertical?: boolean;
}

export function Separator({ style, vertical = false }: SeparatorProps) {
  return (
    <View
      style={[
        vertical ? styles.vertical : styles.horizontal,
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  horizontal: {
    height: 1,
    backgroundColor: colors.border,
    width: '100%',
  },
  vertical: {
    width: 1,
    backgroundColor: colors.border,
    height: '100%',
  },
});
