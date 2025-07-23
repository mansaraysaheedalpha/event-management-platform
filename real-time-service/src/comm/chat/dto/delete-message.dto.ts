import { IsNotEmpty, IsUUID } from 'class-validator';

/**
 * DTO for deleting a chat message.
 */
export class DeleteMessageDto {
  /**
   * The ID of the message to delete (UUID v4).
   */
  @IsNotEmpty()
  @IsUUID('4')
  messageId: string;

  /**
   * A unique key to prevent duplicate delete requests (UUID v4).
   */
  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
