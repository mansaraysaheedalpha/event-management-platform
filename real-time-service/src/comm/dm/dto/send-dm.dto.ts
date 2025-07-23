import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

/**
 * Data Transfer Object for sending a direct message.
 * Contains recipient ID, message text, and an idempotency key to prevent duplicates.
 */
export class SendDmDto {
  /** UUID v4 of the recipient user. */
  @IsNotEmpty()
  @IsUUID('4')
  recipientId: string;

  /** Text content of the direct message, max 2000 characters. */
  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  text: string;

  /** UUID v4 idempotency key to ensure the request is unique. */
  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
