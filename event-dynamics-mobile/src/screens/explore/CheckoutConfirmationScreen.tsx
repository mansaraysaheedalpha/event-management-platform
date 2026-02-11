import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Share,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { CommonActions } from '@react-navigation/native';
import QRCode from 'react-native-qrcode-svg';
import { GET_ORDER_BY_NUMBER_QUERY } from '@/graphql/payments.graphql';
import { Card, Button, Badge, ScreenSkeleton, TicketCardSkeleton, Separator } from '@/components/ui';
import { analytics } from '@/lib/analytics';
import { colors, typography, spacing } from '@/theme';
import type { ExploreStackParamList } from '@/navigation/types';
import { format } from 'date-fns';

type ConfirmationNav = NativeStackNavigationProp<ExploreStackParamList, 'CheckoutConfirmation'>;
type ConfirmationRoute = RouteProp<ExploreStackParamList, 'CheckoutConfirmation'>;

interface MoneyAmount {
  amount: number;
  currency: string;
  formatted: string;
}

interface OrderItem {
  id: string;
  ticketTypeName: string;
  quantity: number;
  unitPrice: MoneyAmount;
  totalPrice: MoneyAmount;
}

interface OrderByNumber {
  id: string;
  orderNumber: string;
  eventId: string;
  status: string;
  customerEmail: string;
  customerName: string;
  items: OrderItem[];
  subtotal: MoneyAmount;
  discountAmount?: MoneyAmount;
  totalAmount: MoneyAmount;
  completedAt: string;
  createdAt: string;
}

interface OrderByNumberResponse {
  orderByNumber: OrderByNumber;
}

export function CheckoutConfirmationScreen() {
  const navigation = useNavigation<ConfirmationNav>();
  const route = useRoute<ConfirmationRoute>();
  const { orderNumber, eventId } = route.params;

  // Success animation
  const scaleAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.sequence([
      Animated.spring(scaleAnim, {
        toValue: 1,
        tension: 50,
        friction: 7,
        useNativeDriver: true,
      }),
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 400,
        useNativeDriver: true,
      }),
    ]).start();
  }, [scaleAnim, fadeAnim]);

  // Load order details
  const { data, loading } = useQuery<OrderByNumberResponse>(GET_ORDER_BY_NUMBER_QUERY, {
    variables: { orderNumber },
    fetchPolicy: 'network-only',
  });

  const order = data?.orderByNumber;

  const handleShare = async () => {
    if (!order) return;
    try {
      const totalTickets = order.items.reduce((sum, item) => sum + item.quantity, 0);
      await Share.share({
        message: `I just got ${totalTickets} ticket${totalTickets !== 1 ? 's' : ''} for an event! Order #${order.orderNumber}`,
      });
    } catch {
      // User cancelled share
    }
  };

  const handleViewTickets = () => {
    // Reset explore stack so back won't return to checkout
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: 'EventBrowse' }],
      }),
    );
    // Navigate across tabs to Profile > MyTickets
    navigation.dispatch(
      CommonActions.navigate({
        name: 'ProfileTab',
        params: { screen: 'MyTickets' },
      }),
    );
  };

  const handleDone = () => {
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: 'EventBrowse' }],
      }),
    );
  };

  if (loading && !data) {
    return <ScreenSkeleton count={2} ItemSkeleton={TicketCardSkeleton} />;
  }

  if (!order) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.centerContent}>
          <Text style={styles.errorTitle}>Order not found</Text>
          <Button title="Go Home" onPress={handleDone} />
        </View>
      </SafeAreaView>
    );
  }

  const totalTickets = order.items.reduce((sum, item) => sum + item.quantity, 0);
  const completedDate = order.completedAt
    ? format(new Date(order.completedAt), 'MMM d, yyyy h:mm a')
    : '';

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Success checkmark */}
        <Animated.View
          style={[
            styles.successCircle,
            { transform: [{ scale: scaleAnim }] },
          ]}
        >
          <Text style={styles.checkmark}>{'\u2713'}</Text>
        </Animated.View>

        <Animated.View style={[styles.fadeContainer, { opacity: fadeAnim }]}>
          <Text style={styles.successTitle}>Payment Successful!</Text>
          <Text style={styles.successSubtitle}>
            Your {totalTickets} ticket{totalTickets !== 1 ? 's have' : ' has'} been confirmed
          </Text>

          {/* QR Code for check-in */}
          <Card style={styles.qrCard}>
            <Text style={styles.qrLabel}>Show this at check-in</Text>
            <View style={styles.qrContainer}>
              <QRCode
                value={order.orderNumber}
                size={180}
                backgroundColor={colors.background}
                color={colors.primary.navy}
              />
            </View>
            <Text style={styles.orderNumber}>#{order.orderNumber}</Text>
          </Card>

          {/* Order details */}
          <Card style={styles.detailsCard}>
            <Text style={styles.sectionTitle}>Order Details</Text>

            {order.items.map((item) => (
              <View key={item.id} style={styles.itemRow}>
                <View style={styles.itemLeft}>
                  <Text style={styles.itemName}>{item.ticketTypeName}</Text>
                  <Text style={styles.itemQty}>Qty: {item.quantity}</Text>
                </View>
                <Text style={styles.itemPrice}>{item.totalPrice.formatted}</Text>
              </View>
            ))}

            <Separator style={styles.separator} />

            {order.discountAmount && order.discountAmount.amount > 0 && (
              <View style={styles.totalRow}>
                <Text style={styles.discountLabel}>Discount</Text>
                <Text style={styles.discountValue}>-{order.discountAmount.formatted}</Text>
              </View>
            )}

            <View style={styles.totalRow}>
              <Text style={styles.grandTotalLabel}>Total Paid</Text>
              <Text style={styles.grandTotalValue}>{order.totalAmount.formatted}</Text>
            </View>

            {completedDate && (
              <Text style={styles.dateText}>Paid on {completedDate}</Text>
            )}
          </Card>

          {/* Confirmation sent */}
          <View style={styles.confirmationNote}>
            <Text style={styles.confirmationText}>
              A confirmation email has been sent to {order.customerEmail}
            </Text>
          </View>

          {/* Action buttons */}
          <View style={styles.actions}>
            <Button
              title="Share with Friends"
              onPress={handleShare}
              variant="outline"
              fullWidth
            />
            <Button
              title="View My Tickets"
              onPress={handleViewTickets}
              variant="secondary"
              fullWidth
            />
            <Button
              title="Done"
              onPress={handleDone}
              fullWidth
            />
          </View>
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.base,
  },
  scroll: { paddingHorizontal: spacing.xl, paddingBottom: spacing['3xl'] },
  successCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.success,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginTop: spacing['2xl'],
    marginBottom: spacing.base,
  },
  checkmark: { fontSize: 40, color: '#FFFFFF', fontWeight: '700' },
  successTitle: {
    ...typography.h2,
    color: colors.foreground,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  successSubtitle: {
    ...typography.body,
    color: colors.neutral[500],
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  qrCard: {
    alignItems: 'center',
    padding: spacing.xl,
    marginBottom: spacing.base,
  },
  qrLabel: {
    ...typography.label,
    color: colors.neutral[500],
    marginBottom: spacing.base,
  },
  qrContainer: {
    padding: spacing.base,
    backgroundColor: colors.background,
    borderRadius: 12,
  },
  orderNumber: {
    ...typography.h4,
    color: colors.foreground,
    marginTop: spacing.md,
    letterSpacing: 1,
  },
  detailsCard: { padding: spacing.base, marginBottom: spacing.base },
  sectionTitle: {
    ...typography.label,
    color: colors.foreground,
    marginBottom: spacing.md,
  },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  itemLeft: { flex: 1 },
  itemName: { ...typography.body, color: colors.foreground },
  itemQty: { ...typography.caption, color: colors.neutral[500] },
  itemPrice: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  separator: { marginVertical: spacing.md },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 2,
  },
  discountLabel: { ...typography.bodySmall, color: colors.success },
  discountValue: { ...typography.bodySmall, color: colors.success, fontWeight: '500' },
  grandTotalLabel: { ...typography.h4, color: colors.foreground },
  grandTotalValue: { ...typography.h4, color: colors.primary.gold },
  dateText: {
    ...typography.caption,
    color: colors.neutral[400],
    marginTop: spacing.sm,
  },
  confirmationNote: {
    backgroundColor: colors.infoLight,
    padding: spacing.md,
    borderRadius: 8,
    marginBottom: spacing.xl,
  },
  confirmationText: {
    ...typography.bodySmall,
    color: colors.info,
    textAlign: 'center',
  },
  fadeContainer: { flex: 1 },
  actions: { gap: spacing.md },
  errorTitle: { ...typography.h3, color: colors.foreground },
});
