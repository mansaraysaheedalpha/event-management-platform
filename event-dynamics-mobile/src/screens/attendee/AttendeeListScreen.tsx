import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { GET_EVENT_ATTENDEES_QUERY } from '@/graphql/registrations.graphql';
import { Card, Avatar, Input, Badge, ScreenSkeleton, AttendeeRowSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type ListNav = NativeStackNavigationProp<HomeStackParamList, 'AttendeeList'>;
type ListRoute = RouteProp<HomeStackParamList, 'AttendeeList'>;

interface AttendeeUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  imageUrl?: string;
}

interface Attendee {
  id: string;
  user: AttendeeUser;
}

interface AttendeesResponse {
  eventAttendees: Attendee[];
}

export function AttendeeListScreen() {
  const navigation = useNavigation<ListNav>();
  const route = useRoute<ListRoute>();
  const { eventId } = route.params;
  const [search, setSearch] = useState('');

  const { data, loading } = useQuery<AttendeesResponse>(
    GET_EVENT_ATTENDEES_QUERY,
    { variables: { eventId } },
  );

  const attendees = data?.eventAttendees ?? [];

  const filtered = useMemo(() => {
    if (!search.trim()) return attendees;
    const q = search.toLowerCase();
    return attendees.filter(
      (a) =>
        a.user.first_name.toLowerCase().includes(q) ||
        a.user.last_name.toLowerCase().includes(q) ||
        a.user.email.toLowerCase().includes(q),
    );
  }, [attendees, search]);

  const handlePress = useCallback(
    (userId: string) => {
      navigation.navigate('AttendeeProfile', { eventId, userId });
    },
    [navigation, eventId],
  );

  const renderItem = useCallback(
    ({ item }: { item: Attendee }) => (
      <TouchableOpacity onPress={() => handlePress(item.user.id)} activeOpacity={0.8} accessibilityRole="button" accessibilityLabel={`Navigate to ${item.user.first_name} ${item.user.last_name} profile`}>
        <Card style={styles.attendeeCard}>
          <Avatar
            name={`${item.user.first_name} ${item.user.last_name}`}
            uri={item.user.imageUrl}
            size={44}
          />
          <View style={styles.attendeeInfo}>
            <Text style={styles.attendeeName}>
              {item.user.first_name} {item.user.last_name}
            </Text>
            <Text style={styles.attendeeEmail}>{item.user.email}</Text>
          </View>
        </Card>
      </TouchableOpacity>
    ),
    [handlePress],
  );

  if (loading && !data) {
    return <ScreenSkeleton count={8} ItemSkeleton={AttendeeRowSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <View style={styles.titleRow}>
          <Text style={styles.title} accessibilityRole="header">Attendees</Text>
          <Badge variant="default" label={`${attendees.length}`} />
        </View>
      </View>

      <View style={styles.searchWrap}>
        <Input
          placeholder="Search attendees..."
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
        />
      </View>

      {filtered.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>
            {search ? 'No results found' : 'No attendees yet'}
          </Text>
          <Text style={styles.emptyText}>
            {search
              ? 'Try a different search term.'
              : 'Be the first to join this event!'}
          </Text>
        </View>
      ) : (
        <FlashList
          data={filtered}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          estimatedItemSize={72}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: 24, paddingTop: 8 },
  backBtn: { marginBottom: 8 },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { ...typography.h2, color: colors.foreground },
  searchWrap: { paddingHorizontal: 24, paddingBottom: 8 },
  list: { paddingHorizontal: 24, paddingBottom: 24 },
  attendeeCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, marginBottom: 8 },
  attendeeInfo: { flex: 1 },
  attendeeName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  attendeeEmail: { ...typography.caption, color: colors.neutral[400] },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
