import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useMutation } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { PERFORM_PASSWORD_RESET_MUTATION } from '@/graphql/auth.graphql';
import { Button, Input } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { AuthStackParamList } from '@/navigation/types';

type ResetNav = NativeStackNavigationProp<AuthStackParamList, 'ResetPassword'>;
type ResetRoute = RouteProp<AuthStackParamList, 'ResetPassword'>;

export function ResetPasswordScreen() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [success, setSuccess] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const navigation = useNavigation<ResetNav>();
  const route = useRoute<ResetRoute>();
  const { token } = route.params;

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const [resetPassword, { loading }] = useMutation<{ performPasswordReset: boolean }>(PERFORM_PASSWORD_RESET_MUTATION, {
    onCompleted: () => {
      setSuccess(true);
      timerRef.current = setTimeout(() => navigation.navigate('Login'), 3000);
    },
    onError: () => Alert.alert('Reset Failed', 'Could not reset your password. The link may have expired.'),
  });

  const handleReset = () => {
    if (!newPassword.trim() || !confirmPassword.trim()) {
      Alert.alert('Error', 'Please fill in both password fields.');
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'Passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      Alert.alert('Error', 'Password must be at least 8 characters.');
      return;
    }
    resetPassword({
      variables: { input: { resetToken: token, newPassword } },
    });
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text style={styles.title} accessibilityRole="header">Reset Password</Text>
            <Text style={styles.subtitle}>Enter your new password below.</Text>
          </View>

          {success ? (
            <View style={styles.successBox}>
              <Text style={styles.successTitle}>Password Reset!</Text>
              <Text style={styles.successText}>
                Your password has been changed successfully. Redirecting to login...
              </Text>
            </View>
          ) : (
            <View style={styles.form}>
              <Input
                label="New Password"
                placeholder="Create a strong password"
                value={newPassword}
                onChangeText={setNewPassword}
                isPassword
                textContentType="newPassword"
              />

              <Input
                label="Confirm Password"
                placeholder="Re-enter your password"
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                isPassword
                textContentType="newPassword"
              />

              <Button
                title={loading ? 'Resetting...' : 'Reset Password'}
                onPress={handleReset}
                loading={loading}
                fullWidth
                size="lg"
              />
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  header: { alignItems: 'center', marginBottom: 32 },
  title: { ...typography.h2, color: colors.foreground, marginBottom: 8 },
  subtitle: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  form: {},
  successBox: {
    backgroundColor: `${colors.success}15`,
    borderWidth: 1,
    borderColor: `${colors.success}40`,
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
  },
  successTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  successText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
