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
import {
  REGISTER_USER_MUTATION,
  REGISTER_ATTENDEE_MUTATION,
} from '@/graphql/auth.graphql';
import { Button, Input, Card } from '@/components/ui';
import { analytics } from '@/lib/analytics';
import { colors, typography } from '@/theme';
import type { AuthStackParamList } from '@/navigation/types';

type RegisterNav = NativeStackNavigationProp<AuthStackParamList, 'Register'>;
type UserRole = 'organizer' | 'attendee' | null;

interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name?: string;
}

interface RegisterOrgResponse {
  registerUser: { token?: string; user?: AuthUser };
}

interface RegisterAttResponse {
  registerAttendee: { token?: string; user?: AuthUser };
}

export function RegisterScreen() {
  const [selectedRole, setSelectedRole] = useState<UserRole>(null);
  const [formData, setFormData] = useState({
    organization_name: '',
    first_name: '',
    last_name: '',
    email: '',
    password: '',
  });

  const navigation = useNavigation<RegisterNav>();
  const setAuth = useAuthStore((state) => state.setAuth);

  const handleSuccess = (token: string, user: { id: string; email: string; first_name: string; last_name?: string }) => {
    setAuth(token, {
      id: user.id,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name ?? '',
    });
  };

  const [registerOrganizer, { loading: orgLoading }] = useMutation<RegisterOrgResponse>(REGISTER_USER_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.registerUser;
      if (token && user) handleSuccess(token, user);
    },
    onError: () => Alert.alert('Registration Failed', 'Could not create your account. Please check your details and try again.'),
  });

  const [registerAttendee, { loading: attLoading }] = useMutation<RegisterAttResponse>(REGISTER_ATTENDEE_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.registerAttendee;
      if (token && user) handleSuccess(token, user);
    },
    onError: () => Alert.alert('Registration Failed', 'Could not create your account. Please check your details and try again.'),
  });

  const loading = orgLoading || attLoading;

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = () => {
    const { first_name, email, password, organization_name } = formData;
    if (!first_name.trim() || !email.trim() || !password.trim()) {
      Alert.alert('Error', 'Please fill in all required fields.');
      return;
    }

    if (selectedRole === 'organizer') {
      if (!organization_name.trim()) {
        Alert.alert('Error', 'Organization name is required.');
        return;
      }
      registerOrganizer({ variables: { input: formData } });
    } else {
      const { organization_name: _, ...attendeeData } = formData;
      registerAttendee({ variables: { input: attendeeData } });
    }
  };

  // Role selection screen
  if (!selectedRole) {
    return (
      <SafeAreaView style={styles.container}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.header}>
            <Text style={styles.title} accessibilityRole="header">Join Event Dynamics</Text>
            <Text style={styles.subtitle}>How would you like to use Event Dynamics?</Text>
          </View>

          <TouchableOpacity onPress={() => setSelectedRole('organizer')} activeOpacity={0.7} accessibilityRole="button" accessibilityLabel="Select organizer role">
            <Card style={styles.roleCard}>
              <View style={styles.roleIconWrap}>
                <Text style={styles.roleIcon}>O</Text>
              </View>
              <View style={styles.roleTextWrap}>
                <Text style={styles.roleTitle}>I'm an Organizer</Text>
                <Text style={styles.roleDesc}>Create and manage events, track registrations.</Text>
              </View>
            </Card>
          </TouchableOpacity>

          <TouchableOpacity onPress={() => setSelectedRole('attendee')} activeOpacity={0.7} accessibilityRole="button" accessibilityLabel="Select attendee role">
            <Card style={styles.roleCard}>
              <View style={styles.roleIconWrap}>
                <Text style={styles.roleIcon}>A</Text>
              </View>
              <View style={styles.roleTextWrap}>
                <Text style={styles.roleTitle}>I'm an Attendee</Text>
                <Text style={styles.roleDesc}>Discover events, register, and participate.</Text>
              </View>
            </Card>
          </TouchableOpacity>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Already have an account? </Text>
            <TouchableOpacity onPress={() => navigation.navigate('Login')} accessibilityRole="button" accessibilityLabel="Sign In">
              <Text style={styles.footerLink}>Sign In</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // Registration form
  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity onPress={() => setSelectedRole(null)} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back to role selection">
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>

          <View style={styles.header}>
            <View style={styles.badgeWrap}>
              <Text style={styles.badgeText}>
                {selectedRole === 'organizer' ? 'Organizer Account' : 'Attendee Account'}
              </Text>
            </View>
            <Text style={styles.title} accessibilityRole="header">Create Your Account</Text>
            <Text style={styles.subtitle}>
              {selectedRole === 'organizer'
                ? 'Set up your organization and start creating events.'
                : 'Join events and connect with others.'}
            </Text>
          </View>

          <View style={styles.form}>
            {selectedRole === 'organizer' && (
              <Input
                label="Organization Name"
                placeholder="e.g., Acme Events"
                value={formData.organization_name}
                onChangeText={(v) => updateField('organization_name', v)}
              />
            )}

            <View style={styles.row}>
              <View style={styles.halfInput}>
                <Input
                  label="First Name"
                  placeholder="John"
                  value={formData.first_name}
                  onChangeText={(v) => updateField('first_name', v)}
                  autoCapitalize="words"
                />
              </View>
              <View style={styles.halfInput}>
                <Input
                  label="Last Name"
                  placeholder="Doe"
                  value={formData.last_name}
                  onChangeText={(v) => updateField('last_name', v)}
                  autoCapitalize="words"
                />
              </View>
            </View>

            <Input
              label="Email"
              placeholder="you@example.com"
              value={formData.email}
              onChangeText={(v) => updateField('email', v)}
              keyboardType="email-address"
              autoCapitalize="none"
              textContentType="emailAddress"
            />

            <Input
              label="Password"
              placeholder="Create a strong password"
              value={formData.password}
              onChangeText={(v) => updateField('password', v)}
              isPassword
              textContentType="newPassword"
            />

            <Button
              title={loading ? 'Creating Account...' : 'Create Account'}
              onPress={handleSubmit}
              loading={loading}
              fullWidth
              size="lg"
            />
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Already have an account? </Text>
            <TouchableOpacity onPress={() => navigation.navigate('Login')} accessibilityRole="button" accessibilityLabel="Sign In">
              <Text style={styles.footerLink}>Sign In</Text>
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
  scroll: { flexGrow: 1, padding: 24 },
  header: { alignItems: 'center', marginBottom: 24 },
  title: { ...typography.h2, color: colors.foreground, marginBottom: 8 },
  subtitle: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  badgeWrap: {
    backgroundColor: `${colors.primary.gold}20`,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    marginBottom: 12,
  },
  badgeText: { ...typography.caption, color: colors.primary.gold, fontWeight: '600' },
  form: { marginBottom: 24 },
  row: { flexDirection: 'row', gap: 12 },
  halfInput: { flex: 1 },
  backBtn: { marginBottom: 12 },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  roleCard: { flexDirection: 'row', alignItems: 'center', gap: 16, marginBottom: 12 },
  roleIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: `${colors.primary.gold}20`,
    justifyContent: 'center',
    alignItems: 'center',
  },
  roleIcon: { fontSize: 20, fontWeight: '700', color: colors.primary.gold },
  roleTextWrap: { flex: 1 },
  roleTitle: { ...typography.h4, color: colors.foreground, marginBottom: 4 },
  roleDesc: { ...typography.bodySmall, color: colors.neutral[500] },
  footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 8 },
  footerText: { ...typography.bodySmall, color: colors.neutral[500] },
  footerLink: { ...typography.bodySmall, color: colors.primary.gold, fontWeight: '700' },
});
