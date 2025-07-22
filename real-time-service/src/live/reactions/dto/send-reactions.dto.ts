import { IsIn, IsString } from 'class-validator';

// A whitelist of allowed emojis prevents abuse and keeps the feature focused.
const ALLOWED_EMOJIS = ['👍', '❤️', '🎉', '💡', '😂', '👏'];

export class SendReactionDto {
  @IsString()
  @IsIn(ALLOWED_EMOJIS)
  emoji: string;
}
