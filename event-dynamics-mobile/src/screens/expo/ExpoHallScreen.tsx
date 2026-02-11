import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useExpo } from '@/hooks/useExpo';
import { Card, Badge, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';
import type { ExpoBooth } from '@/types/expo';
import { BOOTH_TIER_COLORS } from '@/types/expo';

type Nav = NativeStackNavigationProp<HomeStackParamList, 'ExpoHall'>;
type Route = RouteProp<HomeStackParamList, 'ExpoHall'>;

const BoothCard = React.memo(function BoothCard({
  booth,
  onPress,
}: {
  booth: ExpoBooth;
  onPress: () => void;
}) {
  const tierStyle = BOOTH_TIER_COLORS[booth.tier];
  const onlineStaff = booth.staffPresence.filter((s) => s.status === 'ONLINE');

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8}>
      <Card style={[styles.boothCard, { borderLeftColor: tierStyle.border, borderLeftWidth: 3 }]}>
        <View style={styles.boothHeader}>
          {booth.logoUrl ? (
            <Image
              source={{ uri: booth.logoUrl }}
              style={styles.boothLogo}
              contentFit="contain"
              transition={imageConfig.transition}
              placeholder={{ blurhash: imageConfig.defaultBlurhash }}
              cachePolicy={imageConfig.cachePolicy}
            />
          ) : (
            <View style={[styles.boothLogoPlaceholder, { backgroundColor: tierStyle.bg }]}>
              <Text style={[styles.boothLogoText, { color: tierStyle.color }]}>
                {booth.name.charAt(0)}
              </Text>
            </View>
          )}
          <View style={styles.boothInfo}>
            <Text style={styles.boothName} numberOfLines={1}>
              {booth.name}
            </Text>
            {booth.tagline && (
              <Text style={styles.boothTagline} numberOfLines={1}>
                {booth.tagline}
              </Text>
            )}
            <View style={styles.boothMeta}>
              <View style={[styles.tierBadge, { backgroundColor: tierStyle.bg }]}>
                <Text style={[styles.tierBadgeText, { color: tierStyle.color }]}>
                  {booth.tier}
                </Text>
              </View>
              {booth.category && (
                <Text style={styles.boothCategory}>{booth.category}</Text>
              )}
            </View>
          </View>
        </View>

        <View style={styles.boothFooter}>
          <View style={styles.statRow}>
            <Text style={styles.statText}>
              {booth._count.visits} {booth._count.visits === 1 ? 'visitor' : 'visitors'}
            </Text>
            {onlineStaff.length > 0 && (
              <View style={styles.onlineIndicator}>
                <View style={styles.onlineDot} />
                <Text style={styles.onlineText}>
                  {onlineStaff.length} staff online
                </Text>
              </View>
            )}
          </View>
          <View style={styles.featureRow}>
            {booth.chatEnabled && (
              <View style={styles.featureChip}>
                <Text style={styles.featureChipText}>Chat</Text>
              </View>
            )}
            {booth.resources.length > 0 && (
              <View style={styles.featureChip}>
                <Text style={styles.featureChipText}>
                  {booth.resources.length} resources
                </Text>
              </View>
            )}
          </View>
        </View>
      </Card>
    </TouchableOpacity>
  );
});

export function ExpoHallScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { eventId } = route.params;

  const {
    hall,
    booths,
    isConnected,
    isLoading,
    error,
    categories,
    enterHall,
  } = useExpo({ eventId });

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    enterHall();
  }, [enterHall]);

  const filteredBooths = useMemo(() => {
    let filtered = booths;
    if (selectedCategory) {
      filtered = filtered.filter((b) => b.category === selectedCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (b) =>
          b.name.toLowerCase().includes(q) ||
          b.tagline?.toLowerCase().includes(q) ||
          b.category?.toLowerCase().includes(q),
      );
    }
    // Sort by tier priority then display order
    const tierOrder = { PLATINUM: 0, GOLD: 1, SILVER: 2, BRONZE: 3, STARTUP: 4 };
    return filtered.sort(
      (a, b) => (tierOrder[a.tier] ?? 5) - (tierOrder[b.tier] ?? 5) || a.displayOrder - b.displayOrder,
    );
  }, [booths, selectedCategory, searchQuery]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await enterHall();
    setRefreshing(false);
  }, [enterHall]);

  if (isLoading && !hall) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>
            {hall?.name || 'Expo Hall'}
          </Text>
          {isConnected && (
            <View style={styles.connectedBadge}>
              <View style={styles.connectedDot} />
              <Text style={styles.connectedText}>Live</Text>
            </View>
          )}
        </View>
        <View style={{ width: 40 }} />
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search booths..."
          placeholderTextColor={colors.neutral[400]}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Category filter */}
      {categories.length > 0 && (
        <FlatList
          horizontal
          data={[null, ...categories]}
          keyExtractor={(item) => item || 'all'}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.categoryList}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.categoryChip,
                selectedCategory === item && styles.categoryChipActive,
              ]}
              onPress={() => setSelectedCategory(item)}
            >
              <Text
                style={[
                  styles.categoryChipText,
                  selectedCategory === item && styles.categoryChipTextActive,
                ]}
              >
                {item || 'All'}
              </Text>
            </TouchableOpacity>
          )}
        />
      )}

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Booth list */}
      <FlatList
        data={filteredBooths}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <BoothCard
            booth={item}
            onPress={() =>
              navigation.navigate('BoothDetail', { eventId, boothId: item.id })
            }
          />
        )}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary.gold} />
        }
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No booths found</Text>
            <Text style={styles.emptySubtitle}>
              {searchQuery ? 'Try a different search' : 'Expo booths will appear here'}
            </Text>
          </View>
        }
      />
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
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { ...typography.h4, color: colors.foreground },
  connectedBadge: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  connectedDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.success,
  },
  connectedText: { ...typography.caption, color: colors.success },
  searchContainer: { paddingHorizontal: 16, paddingTop: 12 },
  searchInput: {
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[100],
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  categoryList: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  categoryChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.neutral[100],
    marginRight: 8,
  },
  categoryChipActive: { backgroundColor: colors.primary.gold },
  categoryChipText: { ...typography.bodySmall, color: colors.neutral[600], fontWeight: '500' },
  categoryChipTextActive: { color: colors.primary.navy },
  errorBanner: {
    backgroundColor: colors.destructiveLight,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  errorText: { ...typography.bodySmall, color: colors.destructive },
  listContent: { padding: 16, gap: 12 },
  boothCard: { padding: 14 },
  boothHeader: { flexDirection: 'row', gap: 12 },
  boothLogo: { width: 56, height: 56, borderRadius: 8 },
  boothLogoPlaceholder: {
    width: 56,
    height: 56,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  boothLogoText: { fontSize: 24, fontWeight: '700' },
  boothInfo: { flex: 1 },
  boothName: { ...typography.body, color: colors.foreground, fontWeight: '700' },
  boothTagline: { ...typography.bodySmall, color: colors.neutral[500], marginTop: 2 },
  boothMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  tierBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  tierBadgeText: { ...typography.caption, fontWeight: '600' },
  boothCategory: { ...typography.caption, color: colors.neutral[400] },
  boothFooter: { marginTop: 10, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 },
  statRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  statText: { ...typography.caption, color: colors.neutral[500] },
  onlineIndicator: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  onlineDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success },
  onlineText: { ...typography.caption, color: colors.success },
  featureRow: { flexDirection: 'row', gap: 6, marginTop: 6 },
  featureChip: {
    backgroundColor: colors.neutral[100],
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  featureChipText: { ...typography.caption, color: colors.neutral[600] },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptySubtitle: { ...typography.body, color: colors.neutral[400] },
});
