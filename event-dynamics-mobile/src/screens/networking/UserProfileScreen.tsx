// User profile screen — view another attendee's profile and take actions
import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Linking,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, typography, spacing } from '@/theme';
import { Avatar, Badge, Card, Button } from '@/components/ui';
import type { NetworkingStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<NetworkingStackParamList, 'UserProfile'>;
type Route = RouteProp<NetworkingStackParamList, 'UserProfile'>;

export function UserProfileScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { userId } = route.params;

  const [isConnected, setIsConnected] = useState(false);

  const handleMessage = useCallback(() => {
    navigation.navigate('Conversation', {
      userId,
      userName: userId,
    });
  }, [userId, navigation]);

  const handleConnect = useCallback(() => {
    setIsConnected(true);
  }, []);

  const handleLinkedIn = useCallback((url: string) => {
    if (url.startsWith('https://') || url.startsWith('http://')) {
      Linking.openURL(url).catch(() => {
        Alert.alert('Error', 'Could not open LinkedIn profile');
      });
    }
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>{'‹'}</Text>
        </Pressable>
        <Text style={styles.headerTitle}>Profile</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Profile Card */}
        <View style={styles.profileSection}>
          <Avatar name={userId} size={80} />
          <Text style={styles.name}>Attendee Profile</Text>
          <Text style={styles.userId}>ID: {userId}</Text>
        </View>

        {/* Action Buttons */}
        <View style={styles.actions}>
          {isConnected ? (
            <View style={styles.connectedBanner}>
              <Badge label="Connected" variant="success" />
            </View>
          ) : (
            <Button
              title="Connect"
              onPress={handleConnect}
              variant="primary"
              fullWidth
            />
          )}
          <Button
            title="Send Message"
            onPress={handleMessage}
            variant="outline"
            fullWidth
          />
        </View>

        {/* Info Sections */}
        <Card style={styles.section}>
          <View style={styles.sectionContent}>
            <Text style={styles.sectionTitle}>About</Text>
            <Text style={styles.sectionText}>
              Profile details are not yet available.
            </Text>
          </View>
        </Card>

        <Card style={styles.section}>
          <View style={styles.sectionContent}>
            <Text style={styles.sectionTitle}>Shared Interests</Text>
            <Text style={styles.sectionText}>
              Connect to discover shared interests and conversation topics.
            </Text>
          </View>
        </Card>

        <Card style={styles.section}>
          <View style={styles.sectionContent}>
            <Text style={styles.sectionTitle}>Mutual Connections</Text>
            <Text style={styles.sectionText}>
              See who you both know after connecting.
            </Text>
          </View>
        </Card>
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
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: {
    padding: spacing.xs,
    width: 40,
  },
  backText: {
    fontSize: 28,
    color: colors.primary.navy,
    fontWeight: '300',
    lineHeight: 28,
  },
  headerTitle: {
    ...typography.h3,
    color: colors.foreground,
    flex: 1,
    textAlign: 'center',
  },
  headerSpacer: {
    width: 40,
  },
  scrollContent: {
    padding: spacing.base,
  },
  profileSection: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  name: {
    ...typography.h2,
    color: colors.foreground,
    marginTop: spacing.md,
  },
  detail: {
    ...typography.body,
    color: colors.neutral[500],
    marginTop: spacing.xs,
  },
  userId: {
    ...typography.caption,
    color: colors.neutral[400],
    marginTop: spacing.xs,
  },
  actions: {
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  connectedBanner: {
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  section: {
    marginBottom: spacing.md,
  },
  sectionContent: {
    padding: spacing.base,
  },
  sectionTitle: {
    ...typography.h4,
    color: colors.foreground,
    marginBottom: spacing.sm,
  },
  sectionText: {
    ...typography.body,
    color: colors.neutral[500],
  },
});
