import React, { useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { useNavigation } from '@react-navigation/native';
import { Image } from 'expo-image';
import QRCode from 'react-native-qrcode-svg';
import { GET_MY_ORDERS_QUERY } from '@/graphql/payments.graphql';
import { Card, Badge, Separator, Button, ScreenSkeleton, TicketCardSkeleton } from '@/components/ui';
import { imageConfig } from '@/lib/image-config';
import { colors, typography, spacing } from '@/theme';
import { format, isPast } from 'date-fns';

interface OrderEvent {
  id: string;
  name: string;
  startDate: string;
  endDate: string;
  imageUrl?: string;
}

interface OrderItem {
  id: string;
  ticketTypeName: string;
  quantity: number;
}

interface MoneyAmount {
  amount: number;
  currency: string;
  formatted: string;
}

interface OrderNode {
  id: string;
  orderNumber: string;
  event: OrderEvent;
  status: string;
  items: OrderItem[];
  totalAmount: MoneyAmount;
  completedAt: string;
  createdAt: string;
}

interface OrderEdge {
  node: OrderNode;
  cursor: string;
}

interface MyOrdersResponse {
  myOrders: {
    edges: OrderEdge[];
    pageInfo: { hasNextPage: boolean; endCursor: string };
    totalCount: number;
  };
}

type TabFilter = 'upcoming' | 'past';

export function MyTicketsScreen() {
  const navigation = useNavigation();
  const [activeTab, setActiveTab] = useState<TabFilter>('upcoming');
  const [selectedTicket, setSelectedTicket] = useState<OrderNode | null>(null);

  const { data, loading, refetch } = useQuery<MyOrdersResponse>(GET_MY_ORDERS_QUERY, {
    variables: { status: 'COMPLETED', first: 50 },
    fetchPolicy: 'cache-and-network',
  });

  const orders = useMemo(() => {
    return data?.myOrders?.edges?.map((e) => e.node) ?? [];
  }, [data]);

  const filteredOrders = useMemo(() => {
    const now = new Date();
    return orders.filter((order) => {
      const eventEnd = new Date(order.event.endDate);
      if (activeTab === 'upcoming') return eventEnd >= now;
      return eventEnd < now;
    });
  }, [orders, activeTab]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const renderTicketCard = useCallback(
    ({ item }: { item: OrderNode }) => {
      const ticketSummary = item.items
        .map((i) => `${i.quantity}x ${i.ticketTypeName}`)
        .join(', ');

      const eventDate = format(new Date(item.event.startDate), 'EEE, MMM d, yyyy');
      const eventPast = isPast(new Date(item.event.endDate));

      return (
        <TouchableOpacity
          onPress={() => setSelectedTicket(item)}
          activeOpacity={0.7}
        >
          <Card style={[styles.ticketCard, eventPast && styles.ticketCardPast]}>
            <View style={styles.ticketHeader}>
              {item.event.imageUrl && (
                <Image
                  source={{ uri: item.event.imageUrl }}
                  style={styles.eventImage}
                  contentFit="cover"
                  placeholder={{ blurhash: imageConfig.defaultBlurhash }}
                  cachePolicy={imageConfig.cachePolicy}
                  transition={imageConfig.transition}
                />
              )}
              <View style={styles.ticketInfo}>
                <Text style={styles.eventName} numberOfLines={2}>
                  {item.event.name}
                </Text>
                <Text style={styles.eventDate}>{eventDate}</Text>
                <Text style={styles.ticketSummary}>{ticketSummary}</Text>
              </View>
            </View>

            <Separator style={styles.separator} />

            <View style={styles.ticketFooter}>
              <View style={styles.qrPreview}>
                <QRCode
                  value={item.orderNumber}
                  size={40}
                  backgroundColor={colors.background}
                  color={colors.primary.navy}
                />
              </View>
              <View style={styles.ticketMeta}>
                <Text style={styles.orderNumberText}>#{item.orderNumber}</Text>
                <Text style={styles.amountText}>{item.totalAmount.formatted}</Text>
              </View>
              <Badge
                variant={eventPast ? 'default' : 'success'}
                label={eventPast ? 'Past' : 'Active'}
              />
            </View>
          </Card>
        </TouchableOpacity>
      );
    },
    [],
  );

  const renderEmpty = () => (
    <View style={styles.emptyState}>
      <Text style={styles.emptyTitle}>
        {activeTab === 'upcoming' ? 'No upcoming tickets' : 'No past tickets'}
      </Text>
      <Text style={styles.emptyText}>
        {activeTab === 'upcoming'
          ? 'Browse events and purchase tickets to see them here.'
          : 'Your past event tickets will appear here.'}
      </Text>
    </View>
  );

  if (loading && !data) {
    return <ScreenSkeleton count={3} ItemSkeleton={TicketCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>{'\u2190'} Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>My Tickets</Text>
        <Text style={styles.countText}>{orders.length} total</Text>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'upcoming' && styles.tabActive]}
          onPress={() => setActiveTab('upcoming')}
        >
          <Text
            style={[styles.tabText, activeTab === 'upcoming' && styles.tabTextActive]}
          >
            Upcoming
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'past' && styles.tabActive]}
          onPress={() => setActiveTab('past')}
        >
          <Text
            style={[styles.tabText, activeTab === 'past' && styles.tabTextActive]}
          >
            Past
          </Text>
        </TouchableOpacity>
      </View>

      {/* Ticket list */}
      <FlatList
        data={filteredOrders}
        keyExtractor={(item) => item.id}
        renderItem={renderTicketCard}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={renderEmpty}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={handleRefresh} />
        }
      />

      {/* Ticket Detail Modal */}
      <Modal
        visible={!!selectedTicket}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setSelectedTicket(null)}
      >
        {selectedTicket && (
          <TicketDetailModal
            order={selectedTicket}
            onClose={() => setSelectedTicket(null)}
          />
        )}
      </Modal>
    </SafeAreaView>
  );
}

// --- Ticket Detail Modal ---

function TicketDetailModal({
  order,
  onClose,
}: {
  order: OrderNode;
  onClose: () => void;
}) {
  const eventDate = format(new Date(order.event.startDate), 'EEEE, MMMM d, yyyy');
  const eventTime = format(new Date(order.event.startDate), 'h:mm a');

  return (
    <SafeAreaView style={modalStyles.container} edges={['top', 'bottom']}>
      <View style={modalStyles.header}>
        <TouchableOpacity onPress={onClose}>
          <Text style={modalStyles.closeText}>Close</Text>
        </TouchableOpacity>
        <Text style={modalStyles.title}>Ticket Details</Text>
        <View style={modalStyles.headerSpacer} />
      </View>

      <View style={modalStyles.content}>
        {/* Large QR code */}
        <View style={modalStyles.qrSection}>
          <QRCode
            value={order.orderNumber}
            size={220}
            backgroundColor={colors.background}
            color={colors.primary.navy}
          />
          <Text style={modalStyles.orderNumber}>#{order.orderNumber}</Text>
        </View>

        <Separator style={modalStyles.separator} />

        {/* Event info */}
        <View style={modalStyles.infoSection}>
          <Text style={modalStyles.eventName}>{order.event.name}</Text>
          <Text style={modalStyles.infoRow}>{eventDate}</Text>
          <Text style={modalStyles.infoRow}>{eventTime}</Text>
        </View>

        <Separator style={modalStyles.separator} />

        {/* Ticket items */}
        {order.items.map((item) => (
          <View key={item.id} style={modalStyles.itemRow}>
            <Text style={modalStyles.itemName}>{item.ticketTypeName}</Text>
            <Text style={modalStyles.itemQty}>x{item.quantity}</Text>
          </View>
        ))}

        <Separator style={modalStyles.separator} />

        <View style={modalStyles.totalRow}>
          <Text style={modalStyles.totalLabel}>Total Paid</Text>
          <Text style={modalStyles.totalValue}>{order.totalAmount.formatted}</Text>
        </View>

        <Text style={modalStyles.hint}>
          Show this QR code at the event entrance for check-in
        </Text>
      </View>

      <View style={modalStyles.footer}>
        <Button title="Done" onPress={onClose} fullWidth />
      </View>
    </SafeAreaView>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: spacing.xl, paddingTop: spacing.sm, paddingBottom: spacing.md },
  backBtn: { marginBottom: spacing.sm },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  title: { ...typography.h2, color: colors.foreground },
  countText: { ...typography.caption, color: colors.neutral[400], marginTop: 2 },
  tabs: {
    flexDirection: 'row',
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  tab: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: 8,
    backgroundColor: colors.neutral[100],
    alignItems: 'center',
  },
  tabActive: { backgroundColor: colors.primary.gold },
  tabText: { ...typography.label, color: colors.neutral[500] },
  tabTextActive: { color: colors.primary.navy, fontWeight: '700' },
  list: { paddingHorizontal: spacing.xl, paddingBottom: spacing['3xl'] },
  ticketCard: { marginBottom: spacing.md, padding: spacing.base },
  ticketCardPast: { opacity: 0.7 },
  ticketHeader: { flexDirection: 'row', gap: spacing.md },
  eventImage: { width: 60, height: 60, borderRadius: 8, backgroundColor: colors.neutral[100] },
  ticketInfo: { flex: 1 },
  eventName: { ...typography.h4, color: colors.foreground, marginBottom: 2 },
  eventDate: { ...typography.bodySmall, color: colors.neutral[500] },
  ticketSummary: { ...typography.caption, color: colors.neutral[400], marginTop: 2 },
  separator: { marginVertical: spacing.md },
  ticketFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  qrPreview: { padding: 4, backgroundColor: colors.neutral[50], borderRadius: 4 },
  ticketMeta: { flex: 1 },
  orderNumberText: { ...typography.caption, color: colors.neutral[500], letterSpacing: 0.5 },
  amountText: { ...typography.label, color: colors.foreground },
  emptyState: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 80,
  },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: spacing.sm },
  emptyText: {
    ...typography.body,
    color: colors.neutral[500],
    textAlign: 'center',
    paddingHorizontal: spacing.xl,
  },
});

const modalStyles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.base,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  closeText: { ...typography.body, color: colors.primary.gold, fontWeight: '600' },
  title: { ...typography.h4, color: colors.foreground },
  content: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing['2xl'],
  },
  qrSection: { alignItems: 'center', marginBottom: spacing.base },
  orderNumber: {
    ...typography.h3,
    color: colors.foreground,
    marginTop: spacing.md,
    letterSpacing: 1,
  },
  separator: { width: '100%', marginVertical: spacing.base },
  infoSection: { alignItems: 'center', width: '100%' },
  eventName: { ...typography.h3, color: colors.foreground, textAlign: 'center', marginBottom: spacing.xs },
  infoRow: { ...typography.body, color: colors.neutral[500] },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    paddingVertical: spacing.xs,
  },
  itemName: { ...typography.body, color: colors.foreground },
  itemQty: { ...typography.body, color: colors.neutral[500] },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    paddingVertical: spacing.xs,
  },
  totalLabel: { ...typography.h4, color: colors.foreground },
  totalValue: { ...typography.h4, color: colors.primary.gold },
  hint: {
    ...typography.caption,
    color: colors.neutral[400],
    textAlign: 'center',
    marginTop: spacing.xl,
    paddingHorizontal: spacing.xl,
  },
  headerSpacer: { width: 40 },
  footer: {
    padding: spacing.xl,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
});
