// src/common/utils/error.utils.ts

/**
 * Extracts a string message from an unknown error type.
 * @param error - The error object, which can be of any type.
 * @returns A string representing the error message.
 */
export function getErrorMessage(error: unknown): string {
  // If the error is an instance of Error, it has a 'message' property.
  if (error instanceof Error) {
    return error.message;
  }

  // If it's an object with a 'message' property (a common pattern).
  if (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as { message: unknown }).message === 'string'
  ) {
    return (error as { message: string }).message;
  }

  // If it's a string, return it directly.
  if (typeof error === 'string') {
    return error;
  }

  // For other types, or if the message can't be found, serialize it.
  try {
    return JSON.stringify(error);
  } catch {
    return 'An unknown and non-serializable error occurred';
  }
}
