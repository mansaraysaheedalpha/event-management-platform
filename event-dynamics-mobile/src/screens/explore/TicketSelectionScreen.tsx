import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation } from '@apollo/client/react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { GET_EVENT_TICKET_TYPES_QUERY, CREATE_CHECKOUT_SESSION_MUTATION } from '@/graphql/payments.graphql';
import { CREATE_REGISTRATION_MUTATION } from '@/graphql/public.graphql';
import { useAuthStore } from '@/store/auth.store';
import { Card, Badge, Button, ScreenSkeleton, EventCardSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { ExploreStackParamList } from '@/navigation/types';
import { isAboveMinimumCharge } from '@/lib/currency';

type TicketNav = NativeStackNavigationProp<ExploreStackParamList, 'TicketSelection'>;
type TicketRoute = RouteProp<ExploreStackParamList, 'TicketSelection'>;

interface TicketType {
  id: string;
  name: string;
  description?: string;
  price: { amount: number; currency: string; formatted: string };
  quantityTotal: number | null;
  quantityAvailable: number | null;
  minPerOrder: number;
  maxPerOrder: number;
  salesStartAt?: string;
  salesEndAt?: string;
  isOnSale: boolean;
  sortOrder: number;
}

interface TicketTypesResponse {
  eventTicketTypes: TicketType[];
}

interface CreateRegistrationResponse {
  createRegistration: {
    id: string;
    status: string;
    ticketCode: string;
  };
}

interface CheckoutSessionResponse {
  createCheckoutSession: {
    order: {
      id: string;
      orderNumber: string;
    };
    paymentIntent: {
      clientSecret: string;
      intentId: string;
    };
  };
}

function formatPrice(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount / 100);
}

function TicketTypeCard({
  ticket,
  quantity,
  onIncrement,
  onDecrement,
}: {
  ticket: TicketType;
  quantity: number;
  onIncrement: () => void;
  onDecrement: () => void;
}) {
  const isFree = ticket.price.amount === 0;
  const soldOut = ticket.quantityAvailable != null && ticket.quantityAvailable <= 0;
  const limitedStock = ticket.quantityAvailable != null && ticket.quantityAvailable <= 10 && !soldOut;
  const notOnSale = !ticket.isOnSale;

  return (
    <Card style={soldOut || notOnSale ? { ...styles.ticketCard, ...styles.ticketCardDisabled } : styles.ticketCard}>
      <View style={styles.ticketHeader}>
        <View style={styles.ticketTitleRow}>
          <Text style={styles.ticketName}>{ticket.name}</Text>
          <Text style={styles.ticketPrice}>
            {isFree ? 'Free' : formatPrice(ticket.price.amount, ticket.price.currency)}
          </Text>
        </View>
        {ticket.description && (
          <Text style={styles.ticketDesc}>{ticket.description}</Text>
        )}
        <View style={styles.badgeRow}>
          {soldOut && <Badge variant="destructive" label="Sold Out" />}
          {limitedStock && (
            <Badge variant="warning" label={`Only ${ticket.quantityAvailable} left`} />
          )}
          {notOnSale && !soldOut && <Badge variant="default" label="Not on sale" />}
          {isFree && !soldOut && ticket.isOnSale && <Badge variant="success" label="Free" />}
        </View>
      </View>

      {!soldOut && ticket.isOnSale && (
        <View style={styles.quantityControl}>
          <TouchableOpacity
            onPress={onDecrement}
            style={[styles.qtyBtn, quantity <= 0 && styles.qtyBtnDisabled]}
            disabled={quantity <= 0}
          >
            <Text style={styles.qtyBtnText}>-</Text>
          </TouchableOpacity>
          <Text style={styles.qtyText}>{quantity}</Text>
          <TouchableOpacity
            onPress={onIncrement}
            style={[
              styles.qtyBtn,
              quantity >= ticket.maxPerOrder && styles.qtyBtnDisabled,
            ]}
            disabled={quantity >= ticket.maxPerOrder}
          >
            <Text style={styles.qtyBtnText}>+</Text>
          </TouchableOpacity>
        </View>
      )}
    </Card>
  );
}

export function TicketSelectionScreen() {
  const navigation = useNavigation<TicketNav>();
  const route = useRoute<TicketRoute>();
  const { eventId } = route.params;
  const user = useAuthStore((s) => s.user);

  const [quantities, setQuantities] = useState<Record<string, number>>({});

  const { data, loading } = useQuery<TicketTypesResponse>(
    GET_EVENT_TICKET_TYPES_QUERY,
    { variables: { eventId } },
  );

  const [createRegistration, { loading: registering }] =
    useMutation<CreateRegistrationResponse>(CREATE_REGISTRATION_MUTATION, {
      onCompleted: (res) => {
        Alert.alert(
          'Registration Successful!',
          `Your ticket code: ${res.createRegistration.ticketCode}`,
          [{ text: 'OK', onPress: () => navigation.goBack() }],
        );
      },
      onError: () => Alert.alert('Registration Failed', 'Could not complete registration. Please try again.'),
    });

  const [createCheckoutSession, { loading: creatingCheckout }] =
    useMutation<CheckoutSessionResponse>(CREATE_CHECKOUT_SESSION_MUTATION);

  const tickets = useMemo(
    () =>
      [...(data?.eventTicketTypes ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [data],
  );

  const totalItems = Object.values(quantities).reduce((sum, q) => sum + q, 0);
  const totalAmount = tickets.reduce((sum, t) => {
    const qty = quantities[t.id] ?? 0;
    return sum + t.price.amount * qty;
  }, 0);

  const handleIncrement = (ticketId: string, maxPerOrder: number) => {
    setQuantities((prev) => {
      const current = prev[ticketId] ?? 0;
      if (current >= maxPerOrder) return prev;
      return { ...prev, [ticketId]: current + 1 };
    });
  };

  const handleDecrement = (ticketId: string) => {
    setQuantities((prev) => {
      const current = prev[ticketId] ?? 0;
      if (current <= 0) return prev;
      return { ...prev, [ticketId]: current - 1 };
    });
  };

  const handleRegister = async () => {
    // For free tickets, create a direct registration
    const freeTickets = tickets.filter(
      (t) => t.price.amount === 0 && (quantities[t.id] ?? 0) > 0,
    );

    if (freeTickets.length > 0 && totalAmount === 0) {
      if (!user) {
        Alert.alert('Sign In Required', 'Please sign in to register for this event.');
        return;
      }
      createRegistration({
        variables: {
          registrationIn: {
            first_name: user.first_name,
            last_name: user.last_name || '',
            email: user.email,
          },
          eventId,
        },
      });
      return;
    }

    // For paid tickets, create a checkout session and navigate
    if (!user) {
      Alert.alert('Sign In Required', 'Please sign in to purchase tickets.');
      return;
    }

    // Get the currency from the first selected ticket
    const firstSelectedTicket = tickets.find((t) => (quantities[t.id] ?? 0) > 0);
    const currency = firstSelectedTicket?.price.currency ?? 'USD';

    if (!isAboveMinimumCharge(totalAmount, currency)) {
      Alert.alert('Minimum Amount', 'Your order does not meet the minimum charge amount.');
      return;
    }

    try {
      const items = tickets
        .filter((t) => (quantities[t.id] ?? 0) > 0)
        .map((t) => ({
          ticketTypeId: t.id,
          quantity: quantities[t.id],
        }));

      const { data: checkoutData } = await createCheckoutSession({
        variables: {
          input: { eventId, items },
        },
      });

      if (checkoutData?.createCheckoutSession) {
        const { order, paymentIntent } = checkoutData.createCheckoutSession;
        navigation.navigate('Checkout', {
          eventId,
          orderId: order.id,
          clientSecret: paymentIntent.clientSecret,
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start checkout';
      Alert.alert('Checkout Error', message);
    }
  };

  if (loading && !data) {
    return <ScreenSkeleton count={4} ItemSkeleton={EventCardSkeleton} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Select Tickets</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {tickets.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No tickets available</Text>
            <Text style={styles.emptyText}>
              Tickets are not yet on sale for this event.
            </Text>
          </View>
        ) : (
          tickets.map((ticket) => (
            <TicketTypeCard
              key={ticket.id}
              ticket={ticket}
              quantity={quantities[ticket.id] ?? 0}
              onIncrement={() => handleIncrement(ticket.id, ticket.maxPerOrder)}
              onDecrement={() => handleDecrement(ticket.id)}
            />
          ))
        )}
      </ScrollView>

      {/* Bottom summary bar */}
      {totalItems > 0 && (
        <View style={styles.summaryBar}>
          <View>
            <Text style={styles.summaryItems}>
              {totalItems} ticket{totalItems !== 1 ? 's' : ''}
            </Text>
            <Text style={styles.summaryTotal}>
              {totalAmount === 0 ? 'Free' : formatPrice(totalAmount)}
            </Text>
          </View>
          <Button
            title={
              registering
                ? 'Registering...'
                : creatingCheckout
                  ? 'Creating order...'
                  : totalAmount === 0
                    ? 'Register Now'
                    : 'Proceed to Checkout'
            }
            onPress={handleRegister}
            loading={registering || creatingCheckout}
            size="lg"
            style={{ minWidth: 160 }}
          />
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 16 },
  backBtn: { marginBottom: 8 },
  backText: { ...typography.bodySmall, color: colors.neutral[500], fontWeight: '600' },
  title: { ...typography.h2, color: colors.foreground },
  scroll: { paddingHorizontal: 24, paddingBottom: 100 },
  ticketCard: { marginBottom: 12, padding: 16 },
  ticketCardDisabled: { opacity: 0.5 },
  ticketHeader: {},
  ticketTitleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  ticketName: { ...typography.h4, color: colors.foreground, flex: 1 },
  ticketPrice: { ...typography.h4, color: colors.primary.gold, marginLeft: 12 },
  ticketDesc: { ...typography.bodySmall, color: colors.neutral[500], marginBottom: 8 },
  badgeRow: { flexDirection: 'row', gap: 8, marginTop: 4, marginBottom: 8 },
  quantityControl: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 20,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  qtyBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary.gold,
    justifyContent: 'center',
    alignItems: 'center',
  },
  qtyBtnDisabled: { backgroundColor: colors.neutral[200] },
  qtyBtnText: { fontSize: 20, fontWeight: '700', color: '#fff' },
  qtyText: { ...typography.h3, color: colors.foreground, minWidth: 30, textAlign: 'center' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  emptyTitle: { ...typography.h3, color: colors.foreground, marginBottom: 8 },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
  summaryBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    paddingBottom: 32,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  summaryItems: { ...typography.bodySmall, color: colors.neutral[500] },
  summaryTotal: { ...typography.h3, color: colors.foreground },
});
