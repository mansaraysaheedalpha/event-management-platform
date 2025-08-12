// This is our "type guard" function.
//src/common/utils/session.utils.ts
import { SessionMetadata } from '../interfaces/session.interface';

/**
 * Type guard to check if an unknown payload conforms to the SessionMetadata interface.
 *
 * @param payload - The unknown payload to check.
 * @returns `true` if the payload matches the SessionMetadata structure.
 */
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
