import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { Avatar, Card, Button } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type ProfileNav = NativeStackNavigationProp<HomeStackParamList, 'AttendeeProfile'>;
type ProfileRoute = RouteProp<HomeStackParamList, 'AttendeeProfile'>;

export function AttendeeProfileScreen() {
  const navigation = useNavigation<ProfileNav>();
  const route = useRoute<ProfileRoute>();
  const { userId } = route.params;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.content}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>

          <View style={styles.profileHeader}>
            <Avatar name="Attendee" size={80} />
            <Text style={styles.name}>Attendee Profile</Text>
            <Text style={styles.userId}>User ID: {userId}</Text>
          </View>

          <Card style={styles.infoCard}>
            <Text style={styles.infoLabel}>Profile Details</Text>
            <Text style={styles.infoText}>
              Attendee profile details are not yet available.
            </Text>
          </Card>

          <Button
            title="Send Message"
            onPress={() => navigation.goBack()}
            fullWidth
            variant="outline"
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 24 },
  backBtn: { marginBottom: 16 },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  profileHeader: { alignItems: 'center', marginBottom: 24 },
  name: { ...typography.h2, color: colors.foreground, marginTop: 12, marginBottom: 4 },
  userId: { ...typography.caption, color: colors.neutral[400] },
  infoCard: { padding: 16, marginBottom: 24 },
  infoLabel: { ...typography.h4, color: colors.foreground, marginBottom: 8 },
  infoText: { ...typography.body, color: colors.neutral[500], lineHeight: 22 },
});
