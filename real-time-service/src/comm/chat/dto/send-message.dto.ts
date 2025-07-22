import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

/**
 * DTO for sending a chat message.
 */
export class SendMessageDto {
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
  @IsUUID(4)
  idempotencyKey: string;
}
