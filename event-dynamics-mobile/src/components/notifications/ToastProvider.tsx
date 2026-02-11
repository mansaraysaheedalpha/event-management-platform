import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useToast } from '@/hooks/useToast';
import { ToastBanner } from './ToastBanner';

interface ToastProviderProps {
  children: React.ReactNode;
  onNavigate?: (actionUrl: string) => void;
}

export function ToastProvider({ children, onNavigate }: ToastProviderProps) {
  const { toasts, removeToast } = useToast();

  // Only show the newest toast at a time
  const activeToast = toasts[0];

  return (
    <View style={styles.container}>
      {children}
      {activeToast ? (
        <ToastBanner
          key={activeToast.id}
          toast={activeToast}
          onDismiss={removeToast}
          onPress={(actionUrl) => {
            if (actionUrl && onNavigate) onNavigate(actionUrl);
          }}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
