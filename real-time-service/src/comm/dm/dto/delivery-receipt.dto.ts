import { IsUUID } from 'class-validator';

export class DeliveryReceiptDto {
  @IsUUID(4)
  messageId: string;
}
