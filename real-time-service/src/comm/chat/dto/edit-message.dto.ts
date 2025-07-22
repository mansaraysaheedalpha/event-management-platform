import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class EditMessageDto {
  @IsUUID(4)
  messageId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  newText: string;

  @IsUUID(4)
  idempotencyKey: string;
}
