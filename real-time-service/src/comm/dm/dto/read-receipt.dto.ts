//src/comm/dm/dto/read-receipt.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

/**
 * Data Transfer Object for marking a direct message as read.
 * Contains the ID of the message to mark as read.
 */
export class ReadReceiptDto {
  /** UUID v4 of the direct message. */
  @IsNotEmpty()
  @IsUUID('4')
  messageId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
