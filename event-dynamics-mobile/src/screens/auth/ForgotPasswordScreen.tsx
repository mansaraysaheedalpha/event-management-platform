import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { gql } from '@apollo/client';
import { useMutation } from '@apollo/client/react';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Button, Input } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { AuthStackParamList } from '@/navigation/types';

type ForgotNav = NativeStackNavigationProp<AuthStackParamList, 'ForgotPassword'>;

const REQUEST_PASSWORD_RESET_MUTATION = gql`
  mutation RequestPasswordReset($input: RequestResetInput!) {
    requestPasswordReset(input: $input)
  }
`;

export function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  const navigation = useNavigation<ForgotNav>();

  const [requestReset, { loading }] = useMutation<{ requestPasswordReset: boolean }>(REQUEST_PASSWORD_RESET_MUTATION, {
    onCompleted: () => setSent(true),
    onError: () => setSent(true), // Always show success (don't reveal if email exists)
  });

  const handleSubmit = () => {
    if (!email.trim()) {
      Alert.alert('Error', 'Please enter your email address.');
      return;
    }
    requestReset({ variables: { input: { email: email.trim() } } });
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Back to login">
            <Text style={styles.backText}>Back to login</Text>
          </TouchableOpacity>

          <View style={styles.header}>
            <Text style={styles.title} accessibilityRole="header">Forgot Password</Text>
            <Text style={styles.subtitle}>Enter your email to receive a reset link.</Text>
          </View>

          {sent ? (
            <View style={styles.successBox}>
              <Text style={styles.successTitle}>Check Your Email</Text>
              <Text style={styles.successText}>
                If an account with this email exists, a password reset link has been sent.
              </Text>
              <Button
                title="Back to Login"
                onPress={() => navigation.navigate('Login')}
                variant="outline"
                fullWidth
                style={{ marginTop: 16 }}
              />
            </View>
          ) : (
            <View style={styles.form}>
              <Input
                label="Email"
                placeholder="you@example.com"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                textContentType="emailAddress"
              />
              <Button
                title={loading ? 'Sending...' : 'Send Reset Link'}
                onPress={handleSubmit}
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
  backBtn: { marginBottom: 24 },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  header: { alignItems: 'center', marginBottom: 32 },
  title: { ...typography.h2, color: colors.foreground, marginBottom: 8 },
  subtitle: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  form: {},
  successBox: {
    backgroundColor: `${colors.primary.gold}10`,
    borderWidth: 1,
    borderColor: `${colors.primary.gold}30`,
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
  },
  successTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  successText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
