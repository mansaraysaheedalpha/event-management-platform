// Mobile checkout hook — ported from ../globalconnect/src/hooks/use-checkout.ts
// Manages cart state, checkout session creation, and promo code flow

import { useState, useCallback, useMemo } from 'react';
import { useMutation, useQuery } from '@apollo/client/react';
import {
  GET_EVENT_TICKET_TYPES_QUERY,
  CREATE_CHECKOUT_SESSION_MUTATION,
  APPLY_PROMO_CODE_MUTATION,
  REMOVE_PROMO_CODE_MUTATION,
  CANCEL_ORDER_MUTATION,
} from '@/graphql/payments.graphql';
import { useAuthStore } from '@/store/auth.store';
import { formatAmount } from '@/lib/currency';

// --- Types ---

export interface TicketTypePrice {
  amount: number;
  currency: string;
  formatted: string;
}

export interface TicketType {
  id: string;
  name: string;
  description?: string;
  price: TicketTypePrice;
  quantityTotal: number | null;
  quantityAvailable: number | null;
  minPerOrder: number;
  maxPerOrder: number;
  salesStartAt?: string;
  salesEndAt?: string;
  isOnSale: boolean;
  sortOrder: number;
}

export interface CartItem {
  ticketTypeId: string;
  ticketType: TicketType;
  quantity: number;
}

interface MoneyAmount {
  amount: number;
  currency: string;
  formatted: string;
}

interface OrderItem {
  id: string;
  ticketTypeName: string;
  quantity: number;
  unitPrice: { formatted: string };
  totalPrice: { formatted: string };
}

interface Order {
  id: string;
  orderNumber: string;
  status: string;
  items: OrderItem[];
  subtotal: MoneyAmount;
  discountAmount?: { formatted: string };
  totalAmount: MoneyAmount;
  expiresAt?: string;
}

interface PaymentIntent {
  clientSecret: string;
  intentId: string;
  publishableKey?: string;
  expiresAt?: string;
}

export interface CheckoutSession {
  order: Order;
  paymentIntent: PaymentIntent;
}

interface TicketTypesResponse {
  eventTicketTypes: TicketType[];
}

interface CreateCheckoutResponse {
  createCheckoutSession: CheckoutSession;
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

interface CancelOrderResponse {
  cancelOrder: { id: string; status: string };
}

interface UseCheckoutOptions {
  eventId: string;
}

export function useCheckout({ eventId }: UseCheckoutOptions) {
  const user = useAuthStore((s) => s.user);

  // Cart state
  const [cart, setCart] = useState<CartItem[]>([]);

  // Checkout state
  const [checkoutSession, setCheckoutSession] = useState<CheckoutSession | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Promo code state
  const [promoCode, setPromoCode] = useState('');
  const [promoCodeApplied, setPromoCodeApplied] = useState(false);
  const [promoError, setPromoError] = useState<string | null>(null);

  // Fetch ticket types
  const {
    data: ticketTypesData,
    loading: ticketTypesLoading,
    error: ticketTypesError,
  } = useQuery<TicketTypesResponse>(GET_EVENT_TICKET_TYPES_QUERY, {
    variables: { eventId },
    skip: !eventId,
  });

  const ticketTypes: TicketType[] = useMemo(() => {
    return ticketTypesData?.eventTicketTypes ?? [];
  }, [ticketTypesData]);

  // Mutations
  const [createCheckoutSession, { loading: isCreatingCheckout }] =
    useMutation<CreateCheckoutResponse>(CREATE_CHECKOUT_SESSION_MUTATION);

  const [applyPromoMutation, { loading: isApplyingPromo }] =
    useMutation<ApplyPromoResponse>(APPLY_PROMO_CODE_MUTATION);

  const [removePromoMutation] = useMutation<RemovePromoResponse>(REMOVE_PROMO_CODE_MUTATION);

  const [cancelOrderMutation] = useMutation<CancelOrderResponse>(CANCEL_ORDER_MUTATION);

  // Cart totals
  const { cartTotal, cartCurrency, cartTotalFormatted } = useMemo(() => {
    if (cart.length === 0) {
      return { cartTotal: 0, cartCurrency: 'USD', cartTotalFormatted: '$0.00' };
    }

    const currency = cart[0]?.ticketType.price.currency ?? 'USD';
    const total = cart.reduce(
      (sum, item) => sum + item.ticketType.price.amount * item.quantity,
      0,
    );

    return {
      cartTotal: total,
      cartCurrency: currency,
      cartTotalFormatted: formatAmount(total, currency),
    };
  }, [cart]);

  // Cart actions
  const addToCart = useCallback((ticketType: TicketType, quantity: number = 1) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.ticketTypeId === ticketType.id);

      if (existing) {
        const newQuantity = Math.min(existing.quantity + quantity, ticketType.maxPerOrder);
        return prev.map((item) =>
          item.ticketTypeId === ticketType.id
            ? { ...item, quantity: newQuantity }
            : item,
        );
      }

      return [
        ...prev,
        {
          ticketTypeId: ticketType.id,
          ticketType,
          quantity: Math.min(quantity, ticketType.maxPerOrder),
        },
      ];
    });
  }, []);

  const removeFromCart = useCallback((ticketTypeId: string) => {
    setCart((prev) => prev.filter((item) => item.ticketTypeId !== ticketTypeId));
  }, []);

  const updateQuantity = useCallback(
    (ticketTypeId: string, quantity: number) => {
      if (quantity <= 0) {
        removeFromCart(ticketTypeId);
        return;
      }

      setCart((prev) =>
        prev.map((item) => {
          if (item.ticketTypeId !== ticketTypeId) return item;
          const maxQ = item.ticketType.maxPerOrder;
          const minQ = item.ticketType.minPerOrder;
          const validQ = Math.max(minQ, Math.min(quantity, maxQ));
          return { ...item, quantity: validQ };
        }),
      );
    },
    [removeFromCart],
  );

  const clearCart = useCallback(() => {
    setCart([]);
    setCheckoutSession(null);
    setCheckoutError(null);
    setPromoCode('');
    setPromoCodeApplied(false);
    setPromoError(null);
  }, []);

  // Create checkout session — returns order + paymentIntent
  const createCheckout = useCallback(async (): Promise<CheckoutSession | null> => {
    if (cart.length === 0) {
      setCheckoutError('Your cart is empty');
      return null;
    }

    setCheckoutError(null);

    try {
      const input = {
        eventId,
        items: cart.map((item) => ({
          ticketTypeId: item.ticketTypeId,
          quantity: item.quantity,
        })),
        promoCode: promoCodeApplied ? promoCode : undefined,
      };

      const { data } = await createCheckoutSession({
        variables: { input },
      });

      if (data?.createCheckoutSession) {
        setCheckoutSession(data.createCheckoutSession);
        return data.createCheckoutSession;
      }

      return null;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create checkout';
      setCheckoutError(message);
      return null;
    }
  }, [cart, eventId, promoCode, promoCodeApplied, createCheckoutSession]);

  // Cancel checkout
  const cancelCheckout = useCallback(async () => {
    if (!checkoutSession?.order?.id) return;

    try {
      await cancelOrderMutation({
        variables: { orderId: checkoutSession.order.id },
      });
      setCheckoutSession(null);
    } catch (error) {
      console.error('[Checkout] Failed to cancel order:', error);
    }
  }, [checkoutSession, cancelOrderMutation]);

  // Promo code actions
  const applyPromoCodeAction = useCallback(async () => {
    if (!checkoutSession?.order?.id || !promoCode.trim()) {
      setPromoError('Enter a promo code');
      return;
    }

    setPromoError(null);

    try {
      const { data } = await applyPromoMutation({
        variables: {
          orderId: checkoutSession.order.id,
          promoCode: promoCode.trim().toUpperCase(),
        },
      });

      if (data?.applyPromoCode) {
        setPromoCodeApplied(true);
        const promo = data.applyPromoCode;
        setCheckoutSession((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            order: {
              ...prev.order,
              totalAmount: { ...prev.order.totalAmount, ...promo.totalAmount },
              promoCode: promo.promoCode,
            },
          } as CheckoutSession;
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid promo code';
      setPromoError(message);
    }
  }, [checkoutSession, promoCode, applyPromoMutation]);

  const removePromoCodeAction = useCallback(async () => {
    if (!checkoutSession?.order?.id) return;

    try {
      const { data } = await removePromoMutation({
        variables: { orderId: checkoutSession.order.id },
      });

      if (data?.removePromoCode) {
        setPromoCode('');
        setPromoCodeApplied(false);
        setPromoError(null);
        const removed = data.removePromoCode;
        setCheckoutSession((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            order: {
              ...prev.order,
              totalAmount: { ...prev.order.totalAmount, ...removed.totalAmount },
              promoCode: undefined,
            },
          } as CheckoutSession;
        });
      }
    } catch (error) {
      console.error('[Checkout] Failed to remove promo code:', error);
    }
  }, [checkoutSession, removePromoMutation]);

  return {
    // Ticket types
    ticketTypes,
    ticketTypesLoading,
    ticketTypesError: ticketTypesError as Error | undefined,

    // Cart state
    cart,
    cartTotal,
    cartCurrency,
    cartTotalFormatted,

    // Cart actions
    addToCart,
    removeFromCart,
    updateQuantity,
    clearCart,

    // Checkout state
    checkoutSession,
    order: checkoutSession?.order ?? null,
    paymentIntent: checkoutSession?.paymentIntent ?? null,
    isCreatingCheckout,
    checkoutError,

    // Checkout actions
    createCheckout,
    cancelCheckout,

    // Promo code
    promoCode,
    promoCodeApplied,
    isApplyingPromo,
    promoError,
    setPromoCode,
    applyPromoCode: applyPromoCodeAction,
    removePromoCode: removePromoCodeAction,
  };
}
