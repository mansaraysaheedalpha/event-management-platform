//src/comm/chat/dto/react-to-message.dto.ts
import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class ReactToMessageDto {
  /**
   * The session ID where the message belongs.
   * Can be a UUID or custom ID format (e.g., evt_xxx, ses_xxx).
   */
  @IsNotEmpty()
  @IsString()
  sessionId: string;

  @IsNotEmpty()
  @IsUUID('4')
  messageId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(8) // Allow for complex emojis
  emoji: string;

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
