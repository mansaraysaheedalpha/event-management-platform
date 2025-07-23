import { IsIn, IsString } from 'class-validator';

/**
 * DTO for sending real-time reactions within a session.
 *
 * Validates that the emoji is a string and part of the approved list.
 * The emoji set is curated to ensure meaningful and respectful communication.
 *
 * @example
 * const dto: SendReactionDto = { emoji: '🔥' };
 */

const ALLOWED_EMOJIS = [
  '👍',
  '❤️',
  '🎉',
  '💡',
  '😂',
  '👏',
  '🔥',
  '🙏',
  '🤝',
  '🚀',
  '🙌',
  '✅',
  '🎶', // Music vibes (especially for live shows)
  '🕺', // Dancing or good vibes
  '📢', // Announcements, engagement, hype
  '📸', // Photo moments or captured memories
  '🌍', // Pan-African unity, global presence
  '🧠', // Smart insight or innovation
  '🤝', // Partnership or networking moments
];

export class SendReactionDto {
  @IsString()
  @IsIn(ALLOWED_EMOJIS)
  emoji: string;
}

// Further improvemnt later is to Allow admin users to customize emojis per event
