import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useExpo } from '@/hooks/useExpo';
import { BoothChatScreen } from '@/screens/expo/BoothChatScreen';
import { Card, Avatar, Badge, ScreenSkeleton, AttendeeRowSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';
import type { ExpoBooth } from '@/types/expo';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'SponsorMessages'>;
type Route = RouteProp<SponsorStackParamList, 'SponsorMessages'>;

export function SponsorMessagesScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId } = route.params;

  const { hall, booths, isLoading, enterHall } = useExpo({ eventId });

  const [selectedBooth, setSelectedBooth] = useState<ExpoBooth | null>(null);

  useEffect(() => {
    enterHall();
  }, [enterHall]);

  // Filter to only booths owned by this sponsor
  const sponsorBooths = booths.filter((b) => b.sponsorId === sponsorId);

  const handleOpenChat = useCallback((booth: ExpoBooth) => {
    setSelectedBooth(booth);
  }, []);

  if (isLoading && !hall) {
    return <ScreenSkeleton count={5} ItemSkeleton={AttendeeRowSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Messages</Text>
        <View style={{ width: 40 }} />
      </View>

      <FlatList
        data={sponsorBooths}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity onPress={() => handleOpenChat(item)} activeOpacity={0.7}>
            <Card style={styles.boothCard}>
              <View style={styles.boothRow}>
                <Avatar uri={item.logoUrl} name={item.name} size={44} />
                <View style={styles.boothInfo}>
                  <Text style={styles.boothName}>{item.name}</Text>
                  <Text style={styles.boothSubtitle}>
                    Booth #{item.boothNumber} - {item._count.visits} visitors
                  </Text>
                </View>
                {item.chatEnabled && (
                  <Badge variant="success" label="Chat" />
                )}
              </View>
            </Card>
          </TouchableOpacity>
        )}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No booth chats</Text>
            <Text style={styles.emptySubtitle}>
              Your booth conversations will appear here
            </Text>
          </View>
        }
      />

      {/* Chat modal */}
      <Modal
        visible={!!selectedBooth}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        {selectedBooth && (
          <BoothChatScreen
            boothId={selectedBooth.id}
            eventId={eventId}
            boothName={selectedBooth.name}
            onClose={() => setSelectedBooth(null)}
          />
        )}
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backText: { ...typography.label, color: colors.primary.gold },
  headerTitle: { ...typography.h4, color: colors.foreground },
  listContent: { padding: 16 },
  boothCard: { padding: 14, marginBottom: 10 },
  boothRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  boothInfo: { flex: 1 },
  boothName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  boothSubtitle: { ...typography.caption, color: colors.neutral[500] },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptySubtitle: { ...typography.body, color: colors.neutral[400] },
});
