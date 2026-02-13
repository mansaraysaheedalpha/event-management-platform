/**
 * Constants for Expo Booth system
 */

// Queue Management
export const QUEUE_ADMISSION_TIMEOUT_MS = 60_000; // 60 seconds for admitted user to enter
export const QUEUE_POSITION_RECALC_BATCH_SIZE = 100; // Max entries to recalculate at once

// Rate Limiting
export const QUEUE_JOIN_RATE_LIMIT_PER_MINUTE = 5; // Max queue joins per user per minute
export const QUEUE_JOIN_RATE_WINDOW_MS = 60_000; // 1 minute window

// Socket Rooms
export const BOOTH_ROOM_PREFIX = 'booth:';
export const BOOTH_STAFF_ROOM_PREFIX = 'booth-staff:';
export const BOOTH_QUEUE_ROOM_PREFIX = 'booth-queue:';
export const EXPO_HALL_ROOM_PREFIX = 'expo:';

// Helper functions
export const getBoothRoom = (boothId: string) => `${BOOTH_ROOM_PREFIX}${boothId}`;
export const getBoothStaffRoom = (boothId: string) =>
  `${BOOTH_STAFF_ROOM_PREFIX}${boothId}`;
export const getBoothQueueRoom = (boothId: string) =>
  `${BOOTH_QUEUE_ROOM_PREFIX}${boothId}`;
export const getExpoHallRoom = (eventId: string) =>
  `${EXPO_HALL_ROOM_PREFIX}${eventId}`;
