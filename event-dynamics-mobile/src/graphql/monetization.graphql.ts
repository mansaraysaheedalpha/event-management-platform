import { gql } from "@apollo/client";

export const GET_EVENT_MONETIZATION_QUERY = gql`
  query GetEventMonetization($eventId: ID!) {
    eventAds(eventId: $eventId) {
      id
      name
      contentType
      mediaUrl
      clickUrl
      isArchived
    }
    eventOffers(eventId: $eventId) {
      id
      title
      description
      price
      originalPrice
      currency
      offerType
      imageUrl
      expiresAt
      isArchived
      inventory {
        total
        available
        sold
        reserved
      }
      placement
      targetSessions
      targetTicketTiers
      stripePriceId
      isActive
      startsAt
    }
  }
`;

// Query for attendees to view active offers
export const GET_ACTIVE_OFFERS_QUERY = gql`
  query GetActiveOffers(
    $eventId: ID!
    $sessionId: ID
    $placement: String!
  ) {
    activeOffers(
      eventId: $eventId
      sessionId: $sessionId
      placement: $placement
    ) {
      id
      title
      description
      price
      originalPrice
      currency
      offerType
      imageUrl
      expiresAt
      inventory {
        total
        available
        sold
      }
      stripePriceId
      placement
      isActive
    }
  }
`;

// Query for user's purchased offers
export const GET_MY_PURCHASED_OFFERS_QUERY = gql`
  query GetMyPurchasedOffers($eventId: ID!) {
    myPurchasedOffers(eventId: $eventId) {
      id
      offer {
        id
        title
        description
        offerType
        imageUrl
      }
      quantity
      unitPrice
      totalPrice
      currency
      fulfillmentStatus
      fulfillmentType
      digitalContent {
        downloadUrl
        accessCode
      }
      trackingNumber
      purchasedAt
      fulfilledAt
    }
  }
`;

export const CREATE_AD_MUTATION = gql`
  mutation CreateAd($adIn: AdCreateInput!) {
    createAd(adIn: $adIn) {
      id
      name
    }
  }
`;

export const DELETE_AD_MUTATION = gql`
  mutation DeleteAd($id: String!) {
    deleteAd(id: $id)
  }
`;

export const CREATE_OFFER_MUTATION = gql`
  mutation CreateOffer($offerIn: OfferCreateInput!) {
    createOffer(offerIn: $offerIn) {
      id
      title
    }
  }
`;

export const DELETE_OFFER_MUTATION = gql`
  mutation DeleteOffer($id: String!) {
    deleteOffer(id: $id)
  }
`;

export const UPDATE_OFFER_MUTATION = gql`
  mutation UpdateOffer($id: String!, $offerIn: OfferUpdateInput!) {
    updateOffer(id: $id, offerIn: $offerIn) {
      id
      title
      description
      price
      originalPrice
      imageUrl
      inventory {
        total
        available
        sold
        reserved
      }
      isActive
      expiresAt
    }
  }
`;

export const PURCHASE_OFFER_MUTATION = gql`
  mutation PurchaseOffer($offerId: String!, $quantity: Int!) {
    purchaseOffer(offerId: $offerId, quantity: $quantity) {
      checkoutSessionId
      stripeCheckoutUrl
      order {
        id
        orderNumber
        status
        totalAmount {
          amount
          currency
        }
      }
    }
  }
`;

// Ads queries for attendees
export const GET_ADS_FOR_CONTEXT_QUERY = gql`
  query GetAdsForContext(
    $eventId: ID!
    $sessionId: ID
    $placement: String!
    $limit: Int
  ) {
    adsForContext(
      eventId: $eventId
      sessionId: $sessionId
      placement: $placement
      limit: $limit
    ) {
      id
      name
      contentType
      mediaUrl
      clickUrl
      displayDuration
      weight
    }
  }
`;

export const TRACK_AD_IMPRESSIONS_MUTATION = gql`
  mutation TrackAdImpressions($impressions: [AdImpressionInput!]!) {
    trackAdImpressions(impressions: $impressions) {
      success
      trackedCount
    }
  }
`;

export const TRACK_AD_CLICK_MUTATION = gql`
  mutation TrackAdClick($adId: String!, $sessionContext: String) {
    trackAdClick(adId: $adId, sessionContext: $sessionContext) {
      success
      redirectUrl
    }
  }
`;

// Analytics queries
export const GET_MONETIZATION_ANALYTICS_QUERY = gql`
  query GetMonetizationAnalytics(
    $eventId: ID!
    $dateFrom: String
    $dateTo: String
    $includeArchived: Boolean = false
  ) {
    monetizationAnalytics(
      eventId: $eventId
      dateFrom: $dateFrom
      dateTo: $dateTo
      includeArchived: $includeArchived
    ) {
      revenue {
        total
        fromOffers
        fromAds
        byDay {
          date
          amount
        }
      }
      offers {
        totalViews
        totalPurchases
        conversionRate
        averageOrderValue
        topPerformers {
          offerId
          title
          revenue
          conversions
        }
      }
      ads {
        totalImpressions
        totalClicks
        averageCTR
        activeAdsCount
        archivedAdsCount
        topPerformers {
          adId
          name
          impressions
          clicks
          ctr
          isArchived
          contentType
        }
        allAdsPerformance {
          adId
          name
          impressions
          clicks
          ctr
          isArchived
          contentType
        }
      }
      waitlist {
        totalJoins
        offersIssued
        acceptanceRate
        averageWaitTimeMinutes
      }
    }
  }
`;

// Waitlist Management Queries (Organizers Only)
export const GET_SESSION_WAITLIST_QUERY = gql`
  query GetSessionWaitlist($sessionId: ID!) {
    sessionWaitlist(sessionId: $sessionId) {
      id
      position
      userId
      user {
        id
        email
        firstName
        lastName
        imageUrl
      }
      sessionId
      status
      priorityTier
      joinedAt
      offerSentAt
      offerExpiresAt
      offerRespondedAt
      leftAt
    }
    sessionCapacity(sessionId: $sessionId) {
      sessionId
      maximumCapacity
      currentAttendance
      availableSpots
      isAvailable
      waitlistCount
    }
  }
`;

export const GET_EVENT_WAITLIST_ANALYTICS_QUERY = gql`
  query GetEventWaitlistAnalytics($eventId: ID!) {
    eventWaitlistAnalytics(eventId: $eventId) {
      totalWaitlistEntries
      activeWaitlistCount
      totalOffersIssued
      totalOffersAccepted
      totalOffersDeclined
      totalOffersExpired
      acceptanceRate
      averageWaitTimeMinutes
      bySession {
        sessionId
        sessionTitle
        waitlistCount
        offersIssued
        acceptanceRate
      }
    }
  }
`;

export const REMOVE_FROM_WAITLIST_MUTATION = gql`
  mutation RemoveFromWaitlist($input: RemoveFromWaitlistInput!) {
    removeFromWaitlist(input: $input) {
      success
      message
    }
  }
`;

export const MANUALLY_ADD_TO_WAITLIST_MUTATION = gql`
  mutation ManuallyAddToWaitlist($input: JoinWaitlistInput!) {
    joinWaitlist(input: $input) {
      success
      message
      entry {
        id
        position
        joinedAt
      }
    }
  }
`;

export const UPDATE_SESSION_CAPACITY_MUTATION = gql`
  mutation UpdateSessionCapacity($input: UpdateCapacityInput!) {
    updateSessionCapacity(input: $input) {
      sessionId
      maximumCapacity
      currentAttendance
      availableSpots
      isAvailable
      offersAutomaticallySent
    }
  }
`;

export const SEND_WAITLIST_OFFER_MUTATION = gql`
  mutation SendWaitlistOffer($input: SendOfferInput!) {
    sendWaitlistOffer(input: $input) {
      id
      sessionId
      userId
      status
      offerSentAt
      offerExpiresAt
    }
  }
`;

export const BULK_SEND_WAITLIST_OFFERS_MUTATION = gql`
  mutation BulkSendWaitlistOffers($input: BulkSendOffersInput!) {
    bulkSendWaitlistOffers(input: $input) {
      success
      offersSent
      message
    }
  }
`;