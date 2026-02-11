import React from 'react';
import {
  View,
  Text,
  ScrollView,
  Pressable,
  StyleSheet,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import Constants from 'expo-constants';
import { colors, typography, spacing, useThemeStore } from '@/theme';
import { useAuthStore } from '@/store/auth.store';
import { Separator } from '@/components/ui';
import { analytics } from '@/lib/analytics';

type ThemePref = 'system' | 'light' | 'dark';

const THEME_OPTIONS: { value: ThemePref; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

function SettingsRow({
  label,
  value,
  onPress,
}: {
  label: string;
  value?: string;
  onPress?: () => void;
}) {
  return (
    <Pressable
      style={styles.row}
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={value ? `${label}: ${value}` : label}
    >
      <Text style={styles.rowLabel}>{label}</Text>
      {value && <Text style={styles.rowValue}>{value}</Text>}
      {onPress && <Text style={styles.rowChevron}>{'\u203A'}</Text>}
    </Pressable>
  );
}

export function SettingsScreen() {
  const navigation = useNavigation();
  const logout = useAuthStore((s) => s.logout);
  const themePref = useThemeStore((s) => s.preference);
  const setThemePref = useThemeStore((s) => s.setPreference);

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: () => {
          analytics.trackEvent('logout');
          logout();
        },
      },
    ]);
  };

  const handleThemeChange = () => {
    const currentIndex = THEME_OPTIONS.findIndex((o) => o.value === themePref);
    const nextIndex = (currentIndex + 1) % THEME_OPTIONS.length;
    const next = THEME_OPTIONS[nextIndex];
    setThemePref(next.value);
    analytics.trackEvent('theme_changed', { theme: next.value });
  };

  const appVersion = Constants.expoConfig?.version ?? '1.0.0';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Pressable
            onPress={() => navigation.goBack()}
            style={styles.backButton}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text style={styles.backText}>{'\u2039'} Back</Text>
          </Pressable>
          <Text style={styles.title} accessibilityRole="header">
            Settings
          </Text>
        </View>

        {/* Appearance */}
        <Text style={styles.sectionTitle}>Appearance</Text>
        <View style={styles.section}>
          <SettingsRow
            label="Theme"
            value={THEME_OPTIONS.find((o) => o.value === themePref)?.label}
            onPress={handleThemeChange}
          />
          <View style={styles.themeChips}>
            {THEME_OPTIONS.map((opt) => (
              <Pressable
                key={opt.value}
                style={[
                  styles.themeChip,
                  themePref === opt.value && styles.themeChipActive,
                ]}
                onPress={() => {
                  setThemePref(opt.value);
                  analytics.trackEvent('theme_changed', { theme: opt.value });
                }}
                accessibilityRole="radio"
                accessibilityState={{ checked: themePref === opt.value }}
                accessibilityLabel={`${opt.label} theme`}
              >
                <Text
                  style={[
                    styles.themeChipText,
                    themePref === opt.value && styles.themeChipTextActive,
                  ]}
                >
                  {opt.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Notifications */}
        <Text style={styles.sectionTitle}>Notifications</Text>
        <View style={styles.section}>
          <SettingsRow
            label="Notification Preferences"
            onPress={() => (navigation as any).navigate('NotificationPreferences')}
          />
        </View>

        {/* About */}
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.section}>
          <SettingsRow label="Version" value={appVersion} />
          <Separator />
          <SettingsRow label="Build" value="1" />
        </View>

        {/* Account */}
        <View style={styles.logoutSection}>
          <Pressable
            style={styles.logoutButton}
            onPress={handleLogout}
            accessibilityRole="button"
            accessibilityLabel="Sign out"
          >
            <Text style={styles.logoutText}>Sign Out</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: 40,
  },
  header: {
    paddingHorizontal: spacing.base,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
  },
  backButton: {
    paddingVertical: spacing.sm,
    minHeight: 44,
    justifyContent: 'center',
  },
  backText: {
    ...typography.body,
    color: colors.primary.gold,
    fontWeight: '600',
  },
  title: {
    ...typography.h2,
    color: colors.foreground,
    marginTop: spacing.xs,
  },
  sectionTitle: {
    ...typography.label,
    color: colors.neutral[500],
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    paddingHorizontal: spacing.base,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  section: {
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    minHeight: 48,
  },
  rowLabel: {
    ...typography.body,
    color: colors.foreground,
    flex: 1,
  },
  rowValue: {
    ...typography.body,
    color: colors.neutral[500],
    marginRight: spacing.sm,
  },
  rowChevron: {
    fontSize: 20,
    color: colors.neutral[400],
  },
  themeChips: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.md,
  },
  themeChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    minHeight: 44,
    justifyContent: 'center',
  },
  themeChipActive: {
    backgroundColor: colors.primary.navy,
    borderColor: colors.primary.navy,
  },
  themeChipText: {
    ...typography.label,
    color: colors.neutral[600],
  },
  themeChipTextActive: {
    color: '#FFFFFF',
  },
  logoutSection: {
    paddingHorizontal: spacing.base,
    paddingTop: spacing['2xl'],
  },
  logoutButton: {
    backgroundColor: colors.destructiveLight,
    borderRadius: 8,
    paddingVertical: spacing.md,
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
  },
  logoutText: {
    ...typography.button,
    color: colors.destructive,
  },
});
