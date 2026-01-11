// src/common/utils/sanitize.utils.ts

/**
 * Sanitizes user input by removing potentially dangerous HTML/script content.
 * This is a defense-in-depth measure - primary XSS protection should be
 * handled at the rendering layer, but sanitizing input provides an extra layer.
 */

/**
 * Strips HTML tags from a string to prevent stored XSS attacks.
 * Preserves the text content while removing all HTML elements.
 *
 * @param input - The string to sanitize
 * @returns The sanitized string with HTML tags removed
 */
export function stripHtmlTags(input: string): string {
  if (!input || typeof input !== 'string') {
    return input;
  }

  // Remove HTML tags while preserving content
  return input
    .replace(/<[^>]*>/g, '') // Remove HTML tags
    .replace(/&lt;/g, '<') // Decode common entities back (will be re-encoded on display)
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, '/')
    .trim();
}

/**
 * Sanitizes text by removing HTML tags and normalizing whitespace.
 * Use this for user-generated content like incident details and resolution notes.
 *
 * @param input - The string to sanitize
 * @returns The sanitized and normalized string
 */
export function sanitizeTextInput(input: string): string {
  if (!input || typeof input !== 'string') {
    return input;
  }

  return stripHtmlTags(input)
    .replace(/\s+/g, ' ') // Normalize multiple spaces to single space
    .trim();
}

/**
 * Transformer function for use with class-transformer @Transform decorator.
 * Sanitizes string values during DTO transformation.
 *
 * @example
 * ```typescript
 * @Transform(({ value }) => sanitizeTransform(value))
 * @IsString()
 * details: string;
 * ```
 */
export function sanitizeTransform(value: unknown): string | unknown {
  if (typeof value === 'string') {
    return sanitizeTextInput(value);
  }
  return value;
}
