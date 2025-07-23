import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

/**
 * DTO for editing an existing chat message.
 */
export class EditMessageDto {
  /**
   * The ID of the message to be edited (UUID v4).
   */
  @IsNotEmpty()
  @IsUUID('4')
  messageId: string;

  /**
   * The new text content for the message, max 1000 characters.
   */
  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  newText: string;

  /**
   * A unique key to prevent duplicate edit requests (UUID v4).
   */
  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
