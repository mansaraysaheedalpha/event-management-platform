/**
 * Centralized event name constants for all monetization WebSocket events.
 *
 * Convention: dot-separated lowercase for namespaced events.
 * All client-server contracts should reference these constants
 * instead of using inline magic strings.
 */
export const MONETIZATION_EVENTS = {
  // Ads
  AD_INJECTED: 'monetization.ad.injected',

  // Upsell offers
  UPSELL_NEW: 'monetization.upsell.new',

  // Waitlist — client-to-server
  WAITLIST_JOIN: 'monetization.waitlist.join',

  // Waitlist — server-to-client
  WAITLIST_OFFER: 'monetization.waitlist.offer',
  WAITLIST_POSITION_UPDATE: 'monetization.waitlist.position_update',
  WAITLIST_OFFER_EXPIRED: 'monetization.waitlist.offer_expired',
} as const;

export type MonetizationEvent =
  (typeof MONETIZATION_EVENTS)[keyof typeof MONETIZATION_EVENTS];
