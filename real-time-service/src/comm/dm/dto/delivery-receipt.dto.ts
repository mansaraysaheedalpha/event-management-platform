//src/comm/dm/dto/delivery-receopt.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

/**
 * Data Transfer Object for marking a direct message as delivered.
 * Contains the ID of the message to mark as delivered.
 */
export class DeliveryReceiptDto {
  /** UUID v4 of the direct message. */
  @IsNotEmpty()
  @IsUUID('4')
  messageId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
