//src/global/dto/request-translation.dto.ts
import { IsIn, IsString, IsUUID } from 'class-validator';

// A subset of common ISO 639-1 language codes. This list would be expanded.
// A much more comprehensive list for our global platform
const SUPPORTED_LANGUAGES = [
  // Major World Languages
  'en', // English
  'es', // Spanish
  'fr', // French
  'de', // German
  'ja', // Japanese
  'pt', // Portuguese
  'ru', // Russian
  'zh', // Chinese
  'ar', // Arabic
  'hi', // Hindi

  // Key African Languages
  'kri', // Krio (Sierra Leone)
  'sw', // Swahili
  'yo', // Yoruba
  'ig', // Igbo
  'zu', // Zulu
  'ha', // Hausa
];

/**
 * Payload sent by client to request a translation of a specific message.
 *
 * - `messageId`: UUID of the message to be translated.
 * - `targetLanguage`: ISO 639-1 language code the message should be translated into.
 *   Only predefined supported languages are accepted.
 */

export class RequestTranslationDto {
  @IsUUID('4')
  messageId: string;

  @IsString()
  @IsIn(SUPPORTED_LANGUAGES)
  targetLanguage: string;
}
