import { IsEnum, IsNotEmpty, IsString, IsUUID } from 'class-validator';

enum ValidationType {
  QR_CODE = 'QR_CODE',
  NFC = 'NFC',
  MANUAL = 'MANUAL',
  MOBILE = 'MOBILE',
}

export class ValidateTicketDto {
  @IsString()
  @IsNotEmpty()
  ticketCode: string;

  @IsEnum(ValidationType)
  validationType: ValidationType;

  @IsUUID(4)
  idempotencyKey: string;
}
