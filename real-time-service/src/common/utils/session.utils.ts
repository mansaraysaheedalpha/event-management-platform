// This is our "type guard" function.

import { SessionMetadata } from '../interfaces/session.interface';

// It checks if an unknown object matches the SessionMetadata interface.
export const isSessionMetadata = (
  payload: unknown,
): payload is SessionMetadata => {
  const p = payload as SessionMetadata;
  return (
    typeof p === 'object' &&
    p !== null &&
    typeof p.eventId === 'string' &&
    typeof p.organizationId === 'string'
  );
};
