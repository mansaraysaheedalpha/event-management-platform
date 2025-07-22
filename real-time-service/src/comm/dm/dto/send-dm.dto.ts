import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

// Based on 'sendDirectMessagePayload' from our spec
export class SendDmDto {
  @IsUUID(4)
  recipientId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  text: string;

  @IsUUID(4)
  idempotencyKey: string;
}
