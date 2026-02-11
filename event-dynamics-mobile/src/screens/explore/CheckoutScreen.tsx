import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useStripe, CardField, CardFieldInput } from '@stripe/stripe-react-native';
import { GET_ORDER_QUERY, APPLY_PROMO_CODE_MUTATION, REMOVE_PROMO_CODE_MUTATION, CANCEL_ORDER_MUTATION } from '@/graphql/payments.graphql';
import { Card, Button, Input, Badge, ScreenSkeleton, EventCardSkeleton, Separator } from '@/components/ui';
import { analytics } from '@/lib/analytics';
import { colors, typography, spacing } from '@/theme';
import type { ExploreStackParamList } from '@/navigation/types';

type CheckoutNav = NativeStackNavigationProp<ExploreStackParamList, 'Checkout'>;
type CheckoutRoute = RouteProp<ExploreStackParamList, 'Checkout'>;

// --- Types ---

interface MoneyAmount {
  amount: number;
  currency: string;
  formatted: string;
}

interface OrderItem {
  id: string;
  ticketType?: { id: string; name: string };
  ticketTypeName: string;
  quantity: number;
  unitPrice: MoneyAmount;
  totalPrice: MoneyAmount;
}

interface Order {
  id: string;
  orderNumber: string;
  event: {
    id: string;
    name: string;
    startDate: string;
    endDate: string;
    imageUrl?: string;
    venue?: { id: string; name: string };
  };
  status: string;
  items: OrderItem[];
  subtotal: MoneyAmount;
  discountAmount?: MoneyAmount;
  taxAmount?: MoneyAmount;
  totalAmount: MoneyAmount;
  promoCode?: {
    id: string;
    code: string;
    discountType: string;
    discountValue: number;
  } | null;
  expiresAt?: string;
}

interface OrderResponse {
  order: Order;
}

interface ApplyPromoResponse {
  applyPromoCode: {
    id: string;
    subtotal: MoneyAmount;
    discountAmount: MoneyAmount;
    totalAmount: MoneyAmount;
    promoCode: { id: string; code: string; discountType: string; discountValue: number };
  };
}

interface RemovePromoResponse {
  removePromoCode: {
    id: string;
    subtotal: MoneyAmount;
    discountAmount: MoneyAmount;
    totalAmount: MoneyAmount;
    promoCode: { id: string } | null;
  };
}

export function CheckoutScreen() {
  const navigation = useNavigation<CheckoutNav>();
  const route = useRoute<CheckoutRoute>();
  const { eventId, orderId, clientSecret } = route.params;

  const { confirmPayment } = useStripe();

  // Local state
  const [cardComplete, setCardComplete] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [promoInput, setPromoInput] = useState('');
  const [promoError, setPromoError] = useState<string | null>(null);

  // Expiry countdown
  const [timeLeft, setTimeLeft] = useState<string | null>(null);

  // Load order details
  const { data, loading, refetch } = useQuery<OrderResponse>(GET_ORDER_QUERY, {
    variables: { id: orderId },
    fetchPolicy: 'network-only',
  });

  const order = data?.order;

  // Mutations
  const [applyPromo, { loading: applyingPromo }] =
    useMutation<ApplyPromoResponse>(APPLY_PROMO_CODE_MUTATION);
  const [removePromo] = useMutation<RemovePromoResponse>(REMOVE_PROMO_CODE_MUTATION);
  const [cancelOrder] = useMutation<{ cancelOrder: { id: string; status: string } }>(CANCEL_ORDER_MUTATION);

  // Order expiry countdown
  useEffect(() => {
    if (!order?.expiresAt) return;

    const updateCountdown = () => {
      const expiresAt = new Date(order.expiresAt!).getTime();
      const now = Date.now();
      const diff = expiresAt - now;

      if (diff <= 0) {
        setTimeLeft(null);
        Alert.alert('Session Expired', 'Your checkout session has expired. Please try again.', [
          { text: 'OK', onPress: () => navigation.goBack() },
        ]);
        return;
      }

      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setTimeLeft(`${mins}:${secs.toString().padStart(2, '0')}`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [order?.expiresAt, navigation]);

  // Handle payment
  const handlePay = useCallback(async () => {
    if (!cardComplete) {
      setPaymentError('Please complete your card details');
      return;
    }

    if (!clientSecret) {
      setPaymentError('Payment session not found. Please try again.');
      return;
    }

    setProcessing(true);
    setPaymentError(null);

    try {
      const { error, paymentIntent } = await confirmPayment(clientSecret, {
        paymentMethodType: 'Card',
      });

      if (error) {
        setPaymentError(error.message);
        setProcessing(false);
        return;
      }

      if (paymentIntent?.status === 'Succeeded') {
        navigation.replace('CheckoutConfirmation', {
          orderNumber: order?.orderNumber ?? '',
          eventId,
        });
      } else {
        setPaymentError('Payment was not completed. Please try again.');
        setProcessing(false);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Payment failed';
      setPaymentError(message);
      setProcessing(false);
    }
  }, [cardComplete, clientSecret, confirmPayment, navigation, order?.orderNumber, eventId]);

  // Apply promo code
  const handleApplyPromo = useCallback(async () => {
    if (!promoInput.trim()) {
      setPromoError('Enter a promo code');
      return;
    }

    setPromoError(null);

    try {
      await applyPromo({
        variables: {
          orderId,
          promoCode: promoInput.trim().toUpperCase(),
        },
      });
      await refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Invalid promo code';
      setPromoError(message);
    }
  }, [promoInput, orderId, applyPromo, refetch]);

  // Remove promo code
  const handleRemovePromo = useCallback(async () => {
    try {
      await removePromo({ variables: { orderId } });
      setPromoInput('');
      setPromoError(null);
      await refetch();
    } catch (err) {
      console.error('[Checkout] Failed to remove promo:', err);
    }
  }, [orderId, removePromo, refetch]);

  // Cancel checkout — releases the pending order on the backend
  const handleCancel = useCallback(() => {
    Alert.alert('Cancel Checkout', 'Are you sure you want to cancel? Your order will be released.', [
      { text: 'Keep Shopping', style: 'cancel' },
      {
        text: 'Cancel Order',
        style: 'destructive',
        onPress: async () => {
          try {
            await cancelOrder({ variables: { orderId } });
          } catch {
            // Order may have already expired — that's fine
          }
          navigation.goBack();
        },
      },
    ]);
  }, [navigation, cancelOrder, orderId]);

  if (loading && !data) {
    return <ScreenSkeleton count={3} ItemSkeleton={EventCardSkeleton} />;
  }

  if (!order) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorTitle}>Order not found</Text>
          <Button title="Go Back" onPress={() => navigation.goBack()} variant="outline" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={handleCancel} style={styles.cancelBtn}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
          <Text style={styles.title}>Checkout</Text>
          {timeLeft && (
            <Badge variant="warning" label={timeLeft} style={styles.timerBadge} />
          )}
        </View>

        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Event name */}
          <Text style={styles.eventName}>{order.event.name}</Text>
          {order.event.venue && (
            <Text style={styles.venueName}>{order.event.venue.name}</Text>
          )}

          {/* Order Summary */}
          <Card style={styles.section}>
            <Text style={styles.sectionTitle}>Order Summary</Text>
            {order.items.map((item) => (
              <View key={item.id} style={styles.orderItem}>
                <View style={styles.orderItemLeft}>
                  <Text style={styles.itemName}>{item.ticketTypeName}</Text>
                  <Text style={styles.itemQty}>x {item.quantity}</Text>
                </View>
                <Text style={styles.itemPrice}>{item.totalPrice.formatted}</Text>
              </View>
            ))}

            <Separator style={styles.separator} />

            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Subtotal</Text>
              <Text style={styles.totalValue}>{order.subtotal.formatted}</Text>
            </View>

            {order.discountAmount && order.discountAmount.amount > 0 && (
              <View style={styles.totalRow}>
                <Text style={[styles.totalLabel, styles.discountLabel]}>Discount</Text>
                <Text style={[styles.totalValue, styles.discountValue]}>
                  -{order.discountAmount.formatted}
                </Text>
              </View>
            )}

            {order.taxAmount && order.taxAmount.amount > 0 && (
              <View style={styles.totalRow}>
                <Text style={styles.totalLabel}>Tax</Text>
                <Text style={styles.totalValue}>{order.taxAmount.formatted}</Text>
              </View>
            )}

            <Separator style={styles.separator} />

            <View style={styles.totalRow}>
              <Text style={styles.grandTotalLabel}>Total</Text>
              <Text style={styles.grandTotalValue}>{order.totalAmount.formatted}</Text>
            </View>
          </Card>

          {/* Promo Code */}
          <Card style={styles.section}>
            <Text style={styles.sectionTitle}>Promo Code</Text>
            {order.promoCode ? (
              <View style={styles.promoApplied}>
                <View style={styles.promoAppliedLeft}>
                  <Badge variant="success" label={order.promoCode.code} />
                  <Text style={styles.promoAppliedText}>Applied</Text>
                </View>
                <TouchableOpacity onPress={handleRemovePromo}>
                  <Text style={styles.promoRemove}>Remove</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View style={styles.promoRow}>
                <View style={styles.promoInputWrap}>
                  <Input
                    value={promoInput}
                    onChangeText={setPromoInput}
                    placeholder="Enter promo code"
                    autoCapitalize="characters"
                  />
                </View>
                <Button
                  title={applyingPromo ? '...' : 'Apply'}
                  onPress={handleApplyPromo}
                  variant="outline"
                  size="sm"
                  loading={applyingPromo}
                  disabled={!promoInput.trim()}
                />
              </View>
            )}
            {promoError && <Text style={styles.promoErrorText}>{promoError}</Text>}
          </Card>

          {/* Payment Method */}
          <Card style={styles.section}>
            <Text style={styles.sectionTitle}>Payment Method</Text>
            <Text style={styles.paymentHint}>Enter your card details below</Text>

            <CardField
              postalCodeEnabled={false}
              placeholders={{ number: '4242 4242 4242 4242' }}
              cardStyle={{
                backgroundColor: colors.neutral[50],
                textColor: colors.foreground,
                borderColor: colors.border,
                borderWidth: 1,
                borderRadius: 8,
                fontSize: 16,
                placeholderColor: colors.neutral[400],
              }}
              style={styles.cardField}
              onCardChange={(cardDetails: CardFieldInput.Details) => {
                setCardComplete(cardDetails.complete);
                if (cardDetails.complete) {
                  setPaymentError(null);
                }
              }}
            />

            {paymentError && (
              <View style={styles.paymentErrorContainer}>
                <Text style={styles.paymentErrorText}>{paymentError}</Text>
              </View>
            )}
          </Card>

          {/* Terms */}
          <Text style={styles.terms}>
            By completing this purchase, you agree to the event's terms and conditions.
            All sales are final unless the event is cancelled.
          </Text>
        </ScrollView>

        {/* Pay Button */}
        <View style={styles.payBar}>
          <Button
            title={
              processing
                ? 'Processing...'
                : `Pay ${order.totalAmount.formatted}`
            }
            onPress={handlePay}
            loading={processing}
            disabled={processing || !cardComplete}
            size="lg"
            fullWidth
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.base,
  },
  cancelBtn: { marginRight: spacing.base },
  cancelText: { ...typography.bodySmall, color: colors.destructive, fontWeight: '600' },
  title: { ...typography.h3, color: colors.foreground, flex: 1 },
  timerBadge: { marginLeft: spacing.sm },
  scroll: { paddingHorizontal: spacing.xl, paddingBottom: 120 },
  eventName: { ...typography.h4, color: colors.foreground, marginBottom: 2 },
  venueName: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: spacing.base },
  section: { marginBottom: spacing.base, padding: spacing.base },
  sectionTitle: { ...typography.label, color: colors.foreground, marginBottom: spacing.md },
  orderItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  orderItemLeft: { flex: 1 },
  itemName: { ...typography.body, color: colors.foreground },
  itemQty: { ...typography.caption, color: colors.neutral[500] },
  itemPrice: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  separator: { marginVertical: spacing.md },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 2,
  },
  totalLabel: { ...typography.bodySmall, color: colors.neutral[500] },
  totalValue: { ...typography.bodySmall, color: colors.foreground, fontWeight: '500' },
  discountLabel: { color: colors.success },
  discountValue: { color: colors.success },
  grandTotalLabel: { ...typography.h4, color: colors.foreground },
  grandTotalValue: { ...typography.h4, color: colors.primary.gold },
  promoRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  promoInputWrap: { flex: 1 },
  promoApplied: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  promoAppliedLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  promoAppliedText: { ...typography.bodySmall, color: colors.success },
  promoRemove: { ...typography.bodySmall, color: colors.destructive, fontWeight: '600' },
  promoErrorText: { ...typography.caption, color: colors.destructive, marginTop: spacing.xs },
  paymentHint: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: spacing.md },
  cardField: { width: '100%', height: 50, marginVertical: spacing.sm },
  paymentErrorContainer: {
    backgroundColor: colors.destructiveLight,
    padding: spacing.md,
    borderRadius: 8,
    marginTop: spacing.sm,
  },
  paymentErrorText: { ...typography.bodySmall, color: colors.destructive },
  terms: {
    ...typography.caption,
    color: colors.neutral[400],
    textAlign: 'center',
    marginTop: spacing.md,
    paddingHorizontal: spacing.base,
  },
  payBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: spacing.base,
    paddingBottom: spacing['2xl'],
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.base,
  },
  errorTitle: { ...typography.h3, color: colors.foreground },
});
