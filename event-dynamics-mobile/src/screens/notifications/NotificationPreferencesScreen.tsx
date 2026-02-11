import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { colors, typography, spacing, borderRadius } from '@/theme';
import { useNotificationStore } from '@/store/notification.store';
import type { NotificationCategory } from '@/types/notifications';

const CATEGORIES: { key: NotificationCategory; label: string; description: string }[] = [
  {
    key: 'event_updates',
    label: 'Event Updates',
    description: 'Session reminders, schedule changes, emergency alerts',
  },
  {
    key: 'messages',
    label: 'Messages',
    description: 'Direct messages and chat mentions',
  },
  {
    key: 'networking',
    label: 'Networking',
    description: 'Connection requests, recommendations',
  },
  {
    key: 'offers',
    label: 'Offers',
    description: 'Special offers and ticket deals',
  },
  {
    key: 'general',
    label: 'General',
    description: 'Achievements, general updates',
  },
];

export function NotificationPreferencesScreen() {
  const navigation = useNavigation();
  const { preferences, updatePreferences } = useNotificationStore();

  const toggleCategory = useCallback(
    (key: NotificationCategory) => {
      updatePreferences({ [key]: !preferences[key] });
    },
    [preferences, updatePreferences],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Notification Preferences</Text>
        <View style={styles.backButton} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Global Mute */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>Global</Text>
          </View>
          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Text style={styles.settingLabel}>Mute All Notifications</Text>
              <Text style={styles.settingDescription}>
                Temporarily silence all notifications
              </Text>
            </View>
            <Switch
              value={preferences.globalMute}
              onValueChange={(value) => updatePreferences({ globalMute: value })}
              trackColor={{ false: colors.neutral[200], true: colors.primary.gold }}
              thumbColor={colors.background}
            />
          </View>
        </View>

        {/* Categories */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>Categories</Text>
          </View>
          {CATEGORIES.map((category) => (
            <View key={category.key} style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[
                  styles.settingLabel,
                  preferences.globalMute && styles.mutedText,
                ]}>
                  {category.label}
                </Text>
                <Text style={styles.settingDescription}>{category.description}</Text>
              </View>
              <Switch
                value={preferences[category.key] && !preferences.globalMute}
                onValueChange={() => toggleCategory(category.key)}
                disabled={preferences.globalMute}
                trackColor={{ false: colors.neutral[200], true: colors.primary.gold }}
                thumbColor={colors.background}
              />
            </View>
          ))}
        </View>

        {/* Quiet Hours */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>Quiet Hours</Text>
          </View>
          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Text style={styles.settingLabel}>Enable Quiet Hours</Text>
              <Text style={styles.settingDescription}>
                Silence notifications during set hours
              </Text>
            </View>
            <Switch
              value={preferences.quietHoursEnabled}
              onValueChange={(value) => updatePreferences({ quietHoursEnabled: value })}
              trackColor={{ false: colors.neutral[200], true: colors.primary.gold }}
              thumbColor={colors.background}
            />
          </View>
          {preferences.quietHoursEnabled && (
            <View style={styles.quietHoursRow}>
              <View style={styles.timeBox}>
                <Text style={styles.timeLabel}>From</Text>
                <Text style={styles.timeValue}>{preferences.quietHoursStart}</Text>
              </View>
              <Text style={styles.timeSeparator}>—</Text>
              <View style={styles.timeBox}>
                <Text style={styles.timeLabel}>To</Text>
                <Text style={styles.timeValue}>{preferences.quietHoursEnd}</Text>
              </View>
            </View>
          )}
        </View>

        {/* Info */}
        <View style={styles.infoBox}>
          <Text style={styles.infoText}>
            Emergency alerts will always be delivered regardless of your preferences.
          </Text>
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: {
    width: 40,
    alignItems: 'center',
  },
  backText: {
    fontSize: 24,
    color: colors.foreground,
  },
  headerTitle: {
    ...typography.h4,
    color: colors.foreground,
  },
  content: {
    paddingBottom: spacing['3xl'],
  },
  section: {
    marginTop: spacing.xl,
  },
  sectionHeaderRow: {
    paddingHorizontal: spacing.base,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    ...typography.caption,
    fontWeight: '600',
    color: colors.neutral[500],
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    backgroundColor: colors.card,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  settingInfo: {
    flex: 1,
    marginRight: spacing.base,
  },
  settingLabel: {
    ...typography.label,
    color: colors.foreground,
  },
  settingDescription: {
    ...typography.caption,
    color: colors.neutral[500],
    marginTop: 2,
  },
  mutedText: {
    color: colors.neutral[400],
  },
  quietHoursRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.base,
    paddingHorizontal: spacing.base,
    backgroundColor: colors.card,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: spacing.base,
  },
  timeBox: {
    alignItems: 'center',
    backgroundColor: colors.neutral[50],
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  timeLabel: {
    ...typography.caption,
    color: colors.neutral[500],
    marginBottom: spacing.xs,
  },
  timeValue: {
    ...typography.h4,
    color: colors.foreground,
  },
  timeSeparator: {
    ...typography.body,
    color: colors.neutral[400],
  },
  infoBox: {
    marginTop: spacing.xl,
    marginHorizontal: spacing.base,
    padding: spacing.base,
    backgroundColor: colors.infoLight,
    borderRadius: borderRadius.lg,
  },
  infoText: {
    ...typography.bodySmall,
    color: colors.info,
  },
});
