import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface TabIconProps {
  name: string;
  color: string;
  size: number;
}

// Minimal text-based tab icons — future agents should replace
// with @expo/vector-icons (Ionicons or Feather) for production
const labels: Record<string, string> = {
  home: 'H',
  search: 'S',
  users: 'N',
  bell: 'A',
  user: 'P',
};

export function TabIcon({ name, color, size }: TabIconProps) {
  return (
    <View style={[styles.wrapper, { width: size, height: size }]}>
      <Text style={[styles.label, { color, fontSize: size * 0.6 }]}>
        {labels[name] ?? name.charAt(0).toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  label: {
    fontWeight: '700',
    textAlign: 'center',
  },
});