//src/comm/dm/dto/delete-dm.dto.ts

import { IsNotEmpty, IsUUID } from 'class-validator';

export class DeleteDmDto {
  @IsUUID('4')
  @IsNotEmpty()
  messageId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
