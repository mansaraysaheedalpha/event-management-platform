//src/shared/redis.constants.ts
// This file's only job is to export our shared tokens.
// It has no other dependencies, which breaks the circular import.

// This file centralizes all Redis keys and channel names for consistency.

// Injection Tokens
export const REDIS_CLIENT = 'REDIS_CLIENT';
export const REDIS_SUBSCRIBER_CLIENT = 'REDIS_SUBSCRIBER_CLIENT';

// Pub/Sub Channels
export const AUDIT_EVENTS_CHANNEL = 'audit-events';
export const ANALYTICS_EVENTS_CHANNEL = 'analytics-events';
export const SYNC_EVENTS_CHANNEL = 'sync-events';
