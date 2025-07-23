import { IsIn, IsString } from 'class-validator';

/**
 * DTO for sending real-time reactions within a session.
 *
 * Validates that the emoji is a string and part of the approved list.
 * The emoji set is curated to ensure meaningful and respectful communication.
 *
 * @example
 * import { plainToInstance } from 'class-transformer';
 * const dto = plainToInstance(SendReactionDto, { emoji: '🔥' });
 */

/**
 * Whitelisted emojis for reactions and their intended meanings:
 *
 * 👍 - Approval or agreement
 * ❤️ - Love or appreciation
 * 🎉 - Celebration
 * 💡 - Idea or suggestion
 * 😂 - Laughter
 * 👏 - Applause
 * 🔥 - Excitement or highlight
 * 🙏 - Gratitude or thanks
 * 🤝 - Partnership or networking
 * 🚀 - Progress or launch
 * 🙌 - Support or encouragement
 * ✅ - Confirmation or success
 * 🎶 - Music vibes (especially for live shows)
 * 🕺 - Dancing or good vibes
 * 📢 - Announcements, engagement, hype
 * 📸 - Photo moments or captured memories
 * 🌍 - Pan-African unity, global presence
 * 🧠 - Smart insight or innovation
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
  '🎶',
  '🕺',
  '📢',
  '📸',
  '🌍',
  '🧠',
];

export class SendReactionDto {
  @IsString()
  @IsIn(ALLOWED_EMOJIS)
  emoji: string;
}

// Further improvement later is to Allow admin users to customize emojis per event
