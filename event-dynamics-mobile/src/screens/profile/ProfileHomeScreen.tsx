import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Avatar, Card, Button } from '@/components/ui';
import { useAuthStore, isOrganizer } from '@/store/auth.store';
import { colors, typography } from '@/theme';
import type { ProfileStackParamList, RootStackParamList } from '@/navigation/types';

type ProfileNav = NativeStackNavigationProp<ProfileStackParamList, 'ProfileHome'>;

export function ProfileHomeScreen() {
  const navigation = useNavigation<ProfileNav>();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const userIsOrganizer = isOrganizer();

  const handleManageEvents = useCallback(() => {
    // Navigate to root-level OrganizerPortal
    const rootNav = navigation.getParent()?.getParent() as
      | NativeStackNavigationProp<RootStackParamList>
      | undefined;
    rootNav?.navigate('OrganizerPortal');
  }, [navigation]);

  const fullName = user ? `${user.first_name} ${user.last_name}` : 'User';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Text style={styles.title} accessibilityRole="header">Profile</Text>

        {/* User info */}
        <View style={styles.userSection}>
          <Avatar name={fullName} uri={user?.imageUrl ?? undefined} size={64} />
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{fullName}</Text>
            <Text style={styles.userEmail}>{user?.email ?? ''}</Text>
          </View>
        </View>

        {/* Organizer section */}
        {userIsOrganizer && (
          <Card style={styles.organizerCard}>
            <Text style={styles.organizerTitle}>Organizer Tools</Text>
            <Text style={styles.organizerDesc}>
              Manage your events, check in attendees, and monitor live sessions.
            </Text>
            <Button
              title="Manage Events"
              onPress={handleManageEvents}
              variant="primary"
              fullWidth
            />
          </Card>
        )}

        {/* Menu items */}
        <View style={styles.menuSection}>
          <TouchableOpacity style={styles.menuItem} onPress={() => navigation.navigate('EditProfile')} accessibilityRole="button" accessibilityLabel="Edit Profile">
            <Text style={styles.menuText}>Edit Profile</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.menuItem} onPress={() => navigation.navigate('MyTickets')} accessibilityRole="button" accessibilityLabel="My Tickets">
            <Text style={styles.menuText}>My Tickets</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.menuItem} onPress={() => navigation.navigate('Settings')} accessibilityRole="button" accessibilityLabel="Settings">
            <Text style={styles.menuText}>Settings</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* Logout */}
        <Button
          title="Log Out"
          onPress={logout}
          variant="outline"
          fullWidth
          style={styles.logoutButton}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 24, paddingBottom: 40 },
  title: { ...typography.h1, color: colors.foreground, paddingTop: 16, marginBottom: 24 },
  userSection: { flexDirection: 'row', alignItems: 'center', gap: 16, marginBottom: 24 },
  userInfo: { flex: 1 },
  userName: { ...typography.h3, color: colors.foreground },
  userEmail: { ...typography.bodySmall, color: colors.neutral[500], marginTop: 2 },
  organizerCard: { padding: 20, marginBottom: 24, gap: 10 },
  organizerTitle: { ...typography.h4, color: colors.primary.gold },
  organizerDesc: { ...typography.bodySmall, color: colors.neutral[400] },
  menuSection: { marginBottom: 24 },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  menuText: { ...typography.body, color: colors.foreground },
  menuArrow: { ...typography.h3, color: colors.neutral[500] },
  logoutButton: { marginTop: 8 },
});
