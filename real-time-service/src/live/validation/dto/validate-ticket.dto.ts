//src/live/validation/dto/validate-ticket.dto.ts
import { IsEnum, IsNotEmpty, IsString, IsUUID } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

/**
 * Enum representing how the ticket is being validated.
 */
export enum ValidationType {
  /** Scanned via QR code */
  QR_CODE = 'QR_CODE',

  /** Detected via NFC chip */
  NFC = 'NFC',

  /** Entered manually */
  MANUAL = 'MANUAL',

  /** Validated from mobile app */
  MOBILE = 'MOBILE',
}

/**
 * Payload used to validate a ticket. Sent from the gateway to the event service.
 *
 * Example:
 * {
 *   ticketCode: 'ABC123XYZ',
 *   validationType: 'QR_CODE',
 *   idempotencyKey: '3f2e3c55-9c1d-44ef-8cd2-33b474b998d0'
 * }
 */
export class ValidateTicketDto {
  /** Ticket code to validate */
  @ApiProperty({
    example: 'ABC123XYZ',
    description: 'Ticket code to validate',
  })
  @IsString()
  @IsNotEmpty()
  ticketCode: string;

  /** The method used to validate (QR, NFC, etc.) */
  @ApiProperty({
    enum: ValidationType,
    example: ValidationType.QR_CODE,
    description: 'The method used to validate (QR, NFC, etc.)',
  })
  @IsEnum(ValidationType)
  validationType: ValidationType;

  /** Unique key to ensure no duplicate validation */
  @ApiProperty({
    example: '3f2e3c55-9c1d-44ef-8cd2-33b474b998d0',
    description: 'Unique key to ensure no duplicate validation',
  })
  @IsUUID('4')
  idempotencyKey: string;
}
