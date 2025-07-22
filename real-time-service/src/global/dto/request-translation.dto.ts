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

export class RequestTranslationDto {
  @IsUUID(4)
  messageId: string;

  @IsString()
  @IsIn(SUPPORTED_LANGUAGES)
  targetLanguage: string;
}
