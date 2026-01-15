//src/comm/chat/dto/send-message.dto.ts
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

/**
 * DTO for sending a chat message.
 */
export class SendMessageDto {
  /**
   * The session ID where the message will be sent.
   * Can be a UUID or custom ID format (e.g., evt_xxx, ses_xxx).
   */
  @IsNotEmpty()
  @IsString()
  sessionId: string;

  /**
   * The text content of the message, max 1000 characters.
   */
  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  text: string;

  /**
   * A unique key to prevent duplicate message submissions (UUID v4).
   */
  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;

  @IsUUID('4')
  @IsOptional() // A message does not have to be a reply
  replyingToMessageId?: string;

  /**
   * The display name of the session (e.g., "Keynote Speech").
   * Used when auto-creating the ChatSession record.
   */
  @IsString()
  @IsOptional()
  @MaxLength(200)
  sessionName?: string;
}
