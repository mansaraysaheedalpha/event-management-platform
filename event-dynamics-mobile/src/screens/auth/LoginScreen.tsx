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
import { useMutation } from '@apollo/client/react';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuthStore } from '@/store/auth.store';
import { LOGIN_USER_MUTATION } from '@/graphql/auth.graphql';
import { Button, Input } from '@/components/ui';
import { colors, typography } from '@/theme';
import { analytics } from '@/lib/analytics';
import type { AuthStackParamList } from '@/navigation/types';

type LoginNav = NativeStackNavigationProp<AuthStackParamList, 'Login'>;

interface LoginResponse {
  login: {
    token?: string;
    user?: { id: string; email: string; first_name: string; last_name?: string };
    requires2FA?: boolean;
    userIdFor2FA?: string;
    onboardingToken?: string;
    isAttendee?: boolean;
    isSponsor?: boolean;
    sponsorCount?: number;
  };
}

export function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const navigation = useNavigation<LoginNav>();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [login, { loading }] = useMutation<LoginResponse>(LOGIN_USER_MUTATION, {
    onCompleted: (data) => {
      const { token, user, requires2FA, userIdFor2FA } = data.login;

      if (requires2FA && userIdFor2FA) {
        navigation.navigate('TwoFactor', { userId: userIdFor2FA, email });
        return;
      }

      if (token && user) {
        analytics.trackEvent('login_success');
        setAuth(token, {
          id: user.id,
          email: user.email,
          first_name: user.first_name,
          last_name: user.last_name ?? '',
        });
        // RootNavigator auto-switches to Main stack when token is set
      }
    },
    onError: () => {
      analytics.trackEvent('login_failed');
      Alert.alert('Login Failed', 'Invalid email or password. Please try again.');
    },
  });

  const handleLogin = () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert('Error', 'Please fill in all fields.');
      return;
    }
    login({ variables: { input: { email: email.trim(), password } } });
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <Text style={styles.title} accessibilityRole="header">Welcome Back</Text>
            <Text style={styles.subtitle}>
              Enter your credentials to access your account.
            </Text>
          </View>

          <View style={styles.form}>
            <Input
              label="Email"
              placeholder="you@example.com"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              textContentType="emailAddress"
            />

            <Input
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              isPassword
              autoComplete="password"
              textContentType="password"
            />

            <TouchableOpacity
              onPress={() => navigation.navigate('ForgotPassword')}
              style={styles.forgotLink}
              accessibilityRole="button"
              accessibilityLabel="Forgot Password"
            >
              <Text style={styles.forgotText}>Forgot Password?</Text>
            </TouchableOpacity>

            <Button
              title={loading ? 'Signing In...' : 'Sign In'}
              onPress={handleLogin}
              loading={loading}
              fullWidth
              size="lg"
            />
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Don't have an account? </Text>
            <TouchableOpacity onPress={() => navigation.navigate('Register')} accessibilityRole="button" accessibilityLabel="Sign Up">
              <Text style={styles.footerLink}>Sign Up</Text>
            </TouchableOpacity>
          </View>
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
  title: { ...typography.h1, color: colors.foreground, marginBottom: 8 },
  subtitle: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  form: { marginBottom: 24 },
  forgotLink: { alignSelf: 'flex-end', marginBottom: 20, marginTop: -8 },
  forgotText: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '600' },
  footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center' },
  footerText: { ...typography.bodySmall, color: colors.neutral[500] },
  footerLink: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '700' },
});
