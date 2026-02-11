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
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useAuthStore } from '@/store/auth.store';
import {
  LOGIN_2FA_MUTATION,
  SEND_2FA_EMAIL_CODE_MUTATION,
  LOGIN_2FA_WITH_EMAIL_MUTATION,
} from '@/graphql/auth.graphql';
import { Button, Input } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { AuthStackParamList } from '@/navigation/types';

type TwoFactorNav = NativeStackNavigationProp<AuthStackParamList, 'TwoFactor'>;
type TwoFactorRoute = RouteProp<AuthStackParamList, 'TwoFactor'>;

type VerifyMode = 'authenticator' | 'email-request' | 'email-verify';

interface AuthUser { id: string; email: string; first_name: string }
interface Login2FAResponse { login2FA: { token?: string; user?: AuthUser } }
interface SendEmailCodeResponse { send2FAEmailBackupCode: { message: string } }
interface LoginEmailCodeResponse { login2FAWithEmailCode: { token?: string; user?: AuthUser } }

export function TwoFactorScreen() {
  const [code, setCode] = useState('');
  const [mode, setMode] = useState<VerifyMode>('authenticator');

  const navigation = useNavigation<TwoFactorNav>();
  const route = useRoute<TwoFactorRoute>();
  const { userId, email } = route.params;
  const setAuth = useAuthStore((state) => state.setAuth);

  const handleAuthSuccess = (token: string, user: { id: string; email: string; first_name: string }) => {
    setAuth(token, {
      id: user.id,
      email: user.email,
      first_name: user.first_name,
      last_name: '',
    });
  };

  const [verify2FA, { loading: verifyLoading }] = useMutation<Login2FAResponse>(LOGIN_2FA_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.login2FA;
      if (token && user) handleAuthSuccess(token, user);
    },
    onError: () => Alert.alert('Verification Failed', 'Invalid code. Please check and try again.'),
  });

  const [sendEmailCode, { loading: sendingEmail }] = useMutation<SendEmailCodeResponse>(SEND_2FA_EMAIL_CODE_MUTATION, {
    onCompleted: () => {
      setMode('email-verify');
      setCode('');
      Alert.alert('Code Sent', 'A verification code has been sent to your email.');
    },
    onError: () => Alert.alert('Error', 'Could not send verification code. Please try again.'),
  });

  const [verifyEmailCode, { loading: emailVerifyLoading }] = useMutation<LoginEmailCodeResponse>(LOGIN_2FA_WITH_EMAIL_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.login2FAWithEmailCode;
      if (token && user) handleAuthSuccess(token, user);
    },
    onError: () => Alert.alert('Verification Failed', 'Invalid code. Please check and try again.'),
  });

  const loading = verifyLoading || emailVerifyLoading;

  const handleCodeChange = (text: string) => {
    // Strip non-numeric characters, limit to 6 digits
    setCode(text.replace(/\D/g, '').slice(0, 6));
  };

  const handleVerify = () => {
    if (code.length !== 6) {
      Alert.alert('Error', 'Please enter the full 6-digit code.');
      return;
    }

    if (mode === 'email-verify') {
      verifyEmailCode({ variables: { input: { userId, code } } });
    } else {
      verify2FA({ variables: { input: { userId, code } } });
    }
  };

  const handleRequestEmailCode = () => {
    sendEmailCode({ variables: { input: { userId } } });
  };

  const maskedEmail = email
    ? `${email.slice(0, 2)}***${email.slice(email.indexOf('@') - 2)}`
    : 'your email';

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
            <View style={styles.iconWrap}>
              <Text style={styles.iconText}>2FA</Text>
            </View>
            <Text style={styles.title} accessibilityRole="header">Two-Factor Authentication</Text>
            <Text style={styles.subtitle}>
              {mode === 'email-verify'
                ? `Enter the 6-digit code sent to ${maskedEmail}.`
                : 'Enter the 6-digit code from your authenticator app.'}
            </Text>
          </View>

          <View style={styles.form}>
            <Input
              label="Verification Code"
              placeholder="000000"
              value={code}
              onChangeText={handleCodeChange}
              keyboardType="number-pad"
              maxLength={6}
              autoFocus
              style={styles.codeInput}
            />

            <Button
              title={loading ? 'Verifying...' : 'Verify'}
              onPress={handleVerify}
              loading={loading}
              fullWidth
              size="lg"
            />

            {mode === 'authenticator' && (
              <View style={styles.altSection}>
                <View style={styles.dividerRow}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>or</Text>
                  <View style={styles.dividerLine} />
                </View>

                <Button
                  title={sendingEmail ? 'Sending...' : 'Send code to my email'}
                  onPress={handleRequestEmailCode}
                  loading={sendingEmail}
                  variant="outline"
                  fullWidth
                />
              </View>
            )}

            {mode === 'email-verify' && (
              <TouchableOpacity
                onPress={() => {
                  setMode('authenticator');
                  setCode('');
                }}
                style={styles.switchLink}
                accessibilityRole="button"
                accessibilityLabel="Use authenticator app instead"
              >
                <Text style={styles.switchText}>Use authenticator app instead</Text>
              </TouchableOpacity>
            )}
          </View>

          <Text style={styles.expiryNote}>
            {mode === 'email-verify'
              ? 'The email code expires in 10 minutes.'
              : 'Codes refresh every 30 seconds.'}
          </Text>
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
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: 16,
    backgroundColor: `${colors.primary.gold}20`,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  iconText: { fontSize: 18, fontWeight: '800', color: colors.primary.gold },
  title: { ...typography.h2, color: colors.foreground, marginBottom: 8 },
  subtitle: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  form: {},
  codeInput: { textAlign: 'center', fontSize: 24, letterSpacing: 8, fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace' }) },
  altSection: { marginTop: 24 },
  dividerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  dividerLine: { flex: 1, height: 1, backgroundColor: colors.neutral[200] },
  dividerText: { ...typography.bodySmall, color: colors.neutral[400], marginHorizontal: 12 },
  switchLink: { alignSelf: 'center', marginTop: 16 },
  switchText: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '600' },
  expiryNote: { ...typography.caption, color: colors.neutral[400], textAlign: 'center', marginTop: 24 },
});
