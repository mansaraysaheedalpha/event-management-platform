// src/graphql/payments.graphql.ts
import { gql } from "@apollo/client";

// ============================================
// Queries
// ============================================

/**
 * Get ticket types for an event (public - for purchase page)
 */
export const GET_EVENT_TICKET_TYPES_QUERY = gql`
  query GetEventTicketTypes($eventId: ID!) {
    eventTicketTypes(eventId: $eventId) {
      id
      name
      description
      price {
        amount
        currency
        formatted
      }
      quantityTotal
      quantityAvailable
      minPerOrder
      maxPerOrder
      salesStartAt
      salesEndAt
      isOnSale
      sortOrder
    }
  }
`;

/**
 * Get order by ID (for checkout page)
 */
export const GET_ORDER_QUERY = gql`
  query GetOrder($id: ID!) {
    order(id: $id) {
      id
      orderNumber
      event {
        id
        name
        startDate
        endDate
        imageUrl
        venue {
          id
          name
        }
      }
      status
      customerEmail
      customerName
      isGuestOrder
      items {
        id
        ticketType {
          id
          name
        }
        ticketTypeName
        quantity
        unitPrice {
          amount
          currency
          formatted
        }
        totalPrice {
          amount
          currency
          formatted
        }
      }
      subtotal {
        amount
        currency
        formatted
      }
      discountAmount {
        amount
        currency
        formatted
      }
      taxAmount {
        amount
        currency
        formatted
      }
      totalAmount {
        amount
        currency
        formatted
      }
      promoCode {
        id
        code
        discountType
        discountValue
      }
      payment {
        id
        status
        amount {
          amount
          currency
          formatted
        }
        paymentMethodType
        paymentMethodBrand
        paymentMethodLast4
        processedAt
      }
      expiresAt
      completedAt
      createdAt
    }
  }
`;

/**
 * Get order by order number (for confirmation page)
 */
export const GET_ORDER_BY_NUMBER_QUERY = gql`
  query GetOrderByNumber($orderNumber: String!) {
    orderByNumber(orderNumber: $orderNumber) {
      id
      orderNumber
      eventId
      status
      customerEmail
      customerName
      isGuestOrder
      items {
        id
        ticketTypeName
        quantity
        unitPrice {
          amount
          currency
          formatted
        }
        totalPrice {
          amount
          currency
          formatted
        }
      }
      subtotal {
        amount
        currency
        formatted
      }
      discountAmount {
        amount
        currency
        formatted
      }
      totalAmount {
        amount
        currency
        formatted
      }
      completedAt
      createdAt
    }
  }
`;

/**
 * Get current user's orders
 */
export const GET_MY_ORDERS_QUERY = gql`
  query GetMyOrders($status: OrderStatus, $first: Int, $after: String) {
    myOrders(status: $status, first: $first, after: $after) {
      edges {
        node {
          id
          orderNumber
          event {
            id
            name
            startDate
            endDate
            imageUrl
          }
          status
          items {
            id
            ticketTypeName
            quantity
          }
          totalAmount {
            amount
            currency
            formatted
          }
          completedAt
          createdAt
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

/**
 * Get orders for an event (organizer only)
 */
export const GET_EVENT_ORDERS_QUERY = gql`
  query GetEventOrders(
    $eventId: ID!
    $status: OrderStatus
    $search: String
    $first: Int
    $after: String
  ) {
    eventOrders(
      eventId: $eventId
      status: $status
      search: $search
      first: $first
      after: $after
    ) {
      edges {
        node {
          id
          orderNumber
          status
          customerEmail
          customerName
          isGuestOrder
          items {
            id
            ticketTypeName
            quantity
            unitPrice {
              formatted
            }
          }
          totalAmount {
            amount
            currency
            formatted
          }
          payment {
            status
            paymentMethodBrand
            paymentMethodLast4
          }
          completedAt
          createdAt
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

/**
 * Get refunds for an order (organizer only)
 */
export const GET_ORDER_REFUNDS_QUERY = gql`
  query GetOrderRefunds($orderId: ID!) {
    orderRefunds(orderId: $orderId) {
      id
      status
      amount {
        amount
        currency
        formatted
      }
      reason
      reasonDetails
      processedAt
      createdAt
    }
  }
`;

// ============================================
// Mutations
// ============================================

/**
 * Create checkout session (order + payment intent)
 */
export const CREATE_CHECKOUT_SESSION_MUTATION = gql`
  mutation CreateCheckoutSession($input: CreateOrderInput!) {
    createCheckoutSession(input: $input) {
      order {
        id
        orderNumber
        status
        items {
          id
          ticketTypeName
          quantity
          unitPrice {
            formatted
          }
          totalPrice {
            formatted
          }
        }
        subtotal {
          amount
          currency
          formatted
        }
        discountAmount {
          formatted
        }
        totalAmount {
          amount
          currency
          formatted
        }
        expiresAt
      }
      paymentIntent {
        clientSecret
        intentId
        publishableKey
        expiresAt
      }
    }
  }
`;

/**
 * Cancel a pending order
 */
export const CANCEL_ORDER_MUTATION = gql`
  mutation CancelOrder($orderId: ID!) {
    cancelOrder(orderId: $orderId) {
      id
      status
    }
  }
`;

/**
 * Apply promo code to pending order
 */
export const APPLY_PROMO_CODE_MUTATION = gql`
  mutation ApplyPromoCode($orderId: ID!, $promoCode: String!) {
    applyPromoCode(orderId: $orderId, promoCode: $promoCode) {
      id
      subtotal {
        formatted
      }
      discountAmount {
        amount
        formatted
      }
      totalAmount {
        amount
        formatted
      }
      promoCode {
        id
        code
        discountType
        discountValue
      }
    }
  }
`;

/**
 * Remove promo code from pending order
 */
export const REMOVE_PROMO_CODE_MUTATION = gql`
  mutation RemovePromoCode($orderId: ID!) {
    removePromoCode(orderId: $orderId) {
      id
      subtotal {
        formatted
      }
      discountAmount {
        formatted
      }
      totalAmount {
        amount
        formatted
      }
      promoCode {
        id
      }
    }
  }
`;

/**
 * Initiate refund (organizer only)
 */
export const INITIATE_REFUND_MUTATION = gql`
  mutation InitiateRefund($input: InitiateRefundInput!) {
    initiateRefund(input: $input) {
      id
      status
      amount {
        amount
        currency
        formatted
      }
      reason
      reasonDetails
      createdAt
    }
  }
`;

/**
 * Cancel pending refund (organizer only)
 */
export const CANCEL_REFUND_MUTATION = gql`
  mutation CancelRefund($refundId: ID!) {
    cancelRefund(refundId: $refundId) {
      id
      status
    }
  }
`;

// ============================================
// Subscriptions
// ============================================

/**
 * Subscribe to order status changes
 */
export const ORDER_STATUS_SUBSCRIPTION = gql`
  subscription OnOrderStatusChanged($orderId: ID!) {
    orderStatusChanged(orderId: $orderId) {
      id
      status
      payment {
        id
        status
      }
      completedAt
    }
  }
`;

/**
 * Subscribe to payment status changes
 */
export const PAYMENT_STATUS_SUBSCRIPTION = gql`
  subscription OnPaymentStatusChanged($orderId: ID!) {
    paymentStatusChanged(orderId: $orderId) {
      id
      status
      amount {
        formatted
      }
      paymentMethodBrand
      paymentMethodLast4
      processedAt
    }
  }
`;

// ============================================
// ORGANIZER: Ticket Type Management
// ============================================

/**
 * Get all ticket types for an event (organizer view - includes inactive)
 */
export const GET_EVENT_TICKET_TYPES_ADMIN_QUERY = gql`
  query GetEventTicketTypesAdmin($eventId: ID!) {
    eventTicketTypesAdmin(eventId: $eventId) {
      id
      name
      description
      price {
        amount
        currency
        formatted
      }
      quantityTotal
      quantityAvailable
      quantitySold
      quantityReserved
      minPerOrder
      maxPerOrder
      salesStartAt
      salesEndAt
      isActive
      isHidden
      isOnSale
      sortOrder
      revenue {
        amount
        currency
        formatted
      }
      createdAt
      updatedAt
    }
  }
`;

/**
 * Get ticket sales summary for an event
 */
export const GET_EVENT_TICKET_SUMMARY_QUERY = gql`
  query GetEventTicketSummary($eventId: ID!) {
    eventTicketSummary(eventId: $eventId) {
      eventId
      totalTicketTypes
      totalCapacity
      totalSold
      totalRevenue {
        amount
        currency
        formatted
      }
      ticketTypeStats {
        ticketTypeId
        ticketTypeName
        quantitySold
        quantityAvailable
        revenue {
          amount
          currency
          formatted
        }
        percentageSold
      }
      salesToday
      salesThisWeek
      salesThisMonth
      revenueToday {
        formatted
      }
      revenueThisWeek {
        formatted
      }
      revenueThisMonth {
        formatted
      }
    }
  }
`;

/**
 * Create a new ticket type
 */
export const CREATE_TICKET_TYPE_MUTATION = gql`
  mutation CreateTicketType($input: TicketTypeCreateInput!) {
    createTicketType(input: $input) {
      id
      name
      description
      price {
        amount
        currency
        formatted
      }
      quantityTotal
      quantityAvailable
      minPerOrder
      maxPerOrder
      salesStartAt
      salesEndAt
      isActive
      isHidden
      isOnSale
      sortOrder
    }
  }
`;

/**
 * Update a ticket type
 */
export const UPDATE_TICKET_TYPE_MUTATION = gql`
  mutation UpdateTicketType($id: ID!, $input: TicketTypeUpdateInput!) {
    updateTicketType(id: $id, input: $input) {
      id
      name
      description
      price {
        amount
        currency
        formatted
      }
      quantityTotal
      quantityAvailable
      quantitySold
      minPerOrder
      maxPerOrder
      salesStartAt
      salesEndAt
      isActive
      isHidden
      isOnSale
      sortOrder
    }
  }
`;

/**
 * Delete a ticket type (only if no sales)
 */
export const DELETE_TICKET_TYPE_MUTATION = gql`
  mutation DeleteTicketType($id: ID!) {
    deleteTicketType(id: $id)
  }
`;

/**
 * Reorder ticket types
 */
export const REORDER_TICKET_TYPES_MUTATION = gql`
  mutation ReorderTicketTypes($input: ReorderTicketTypesInput!) {
    reorderTicketTypes(input: $input) {
      id
      sortOrder
    }
  }
`;

/**
 * Duplicate a ticket type
 */
export const DUPLICATE_TICKET_TYPE_MUTATION = gql`
  mutation DuplicateTicketType($id: ID!) {
    duplicateTicketType(id: $id) {
      id
      name
      description
      price {
        amount
        currency
        formatted
      }
      quantityTotal
      minPerOrder
      maxPerOrder
      salesStartAt
      salesEndAt
      isActive
      sortOrder
    }
  }
`;

// ============================================
// ORGANIZER: Promo Code Management
// ============================================

/**
 * Get promo codes for an event
 */
export const GET_EVENT_PROMO_CODES_QUERY = gql`
  query GetEventPromoCodes($eventId: ID!) {
    eventPromoCodes(eventId: $eventId) {
      id
      code
      description
      discountType
      discountValue
      discountFormatted
      applicableTicketTypes {
        id
        name
      }
      maxUses
      maxUsesPerUser
      currentUses
      remainingUses
      validFrom
      validUntil
      isCurrentlyValid
      minimumOrderAmount {
        amount
        formatted
      }
      minimumTickets
      isActive
      createdAt
    }
  }
`;

/**
 * Create a promo code
 */
export const CREATE_PROMO_CODE_MUTATION = gql`
  mutation CreatePromoCode($input: PromoCodeCreateInput!) {
    createPromoCode(input: $input) {
      id
      code
      description
      discountType
      discountValue
      discountFormatted
      maxUses
      maxUsesPerUser
      validFrom
      validUntil
      isActive
    }
  }
`;

/**
 * Update a promo code
 */
export const UPDATE_PROMO_CODE_MUTATION = gql`
  mutation UpdatePromoCode($id: String!, $input: UpdatePromoCodeInput!) {
    updatePromoCode(id: $id, input: $input) {
      id
      code
      description
      discountType
      discountValue
      discountFormatted
      maxUses
      maxUsesPerUser
      currentUses
      validFrom
      validUntil
      isActive
    }
  }
`;

/**
 * Delete a promo code
 */
export const DELETE_PROMO_CODE_MUTATION = gql`
  mutation DeletePromoCode($id: String!) {
    deletePromoCode(id: $id)
  }
`;


/**
 * Get current user's tickets (for My Tickets screen)
 */
export const GET_MY_TICKETS_QUERY = gql`
  query GetMyTickets {
    myTickets {
      id
      ticketCode
      status
      ticketType {
        id
        name
      }
      event {
        id
        name
        startDate
        endDate
        imageUrl
        venue {
          id
          name
        }
      }
      order {
        id
        orderNumber
      }
      checkedInAt
      createdAt
    }
  }
`;

/**
 * Check in a ticket
 */
export const CHECK_IN_TICKET_MUTATION = gql`
  mutation CheckInTicket($input: CheckInTicketInput!) {
    checkInTicket(input: $input) {
      id
      status
      ticketCode
      checkedInAt
      checkInLocation
    }
  }
`;