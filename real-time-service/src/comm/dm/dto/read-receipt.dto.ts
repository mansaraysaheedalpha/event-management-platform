import { IsUUID } from 'class-validator';

export class ReadReceiptDto {
  @IsUUID(4)
  messageId: string;
}
