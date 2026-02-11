import React, { useState } from 'react';
import {
  View,
  TextInput,
  Text,
  StyleSheet,
  TextInputProps,
  TouchableOpacity,
} from 'react-native';
import { colors, typography } from '@/theme';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
  isPassword?: boolean;
}

export function Input({
  label,
  error,
  isPassword = false,
  style,
  ...props
}: InputProps) {
  const [secureEntry, setSecureEntry] = useState(isPassword);

  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={[styles.inputWrapper, error && styles.inputError]}>
        <TextInput
          style={[styles.input, style]}
          placeholderTextColor={colors.neutral[400]}
          secureTextEntry={secureEntry}
          autoCapitalize={isPassword ? 'none' : undefined}
          accessibilityLabel={label || props.placeholder}
          {...props}
        />
        {isPassword && (
          <TouchableOpacity
            onPress={() => setSecureEntry(!secureEntry)}
            style={styles.toggle}
            accessibilityRole="button"
            accessibilityLabel={secureEntry ? 'Show password' : 'Hide password'}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={styles.toggleText}>
              {secureEntry ? 'Show' : 'Hide'}
            </Text>
          </TouchableOpacity>
        )}
      </View>
      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  label: {
    ...typography.label,
    color: colors.foreground,
    marginBottom: 6,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    backgroundColor: colors.background,
  },
  inputError: {
    borderColor: colors.destructive,
  },
  input: {
    flex: 1,
    ...typography.body,
    color: colors.foreground,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  toggle: {
    paddingHorizontal: 12,
    minHeight: 44,
    justifyContent: 'center' as const,
  },
  toggleText: {
    ...typography.bodySmall,
    color: colors.primary.gold,
    fontWeight: '600',
  },
  error: {
    ...typography.caption,
    color: colors.destructive,
    marginTop: 4,
  },
});
