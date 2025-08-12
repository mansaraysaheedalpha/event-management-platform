//src/comm/dm/dto/delete-dm.dto.ts
import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class EditDmDto {
  @IsUUID('4')
  @IsNotEmpty()
  messageId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  newText: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
