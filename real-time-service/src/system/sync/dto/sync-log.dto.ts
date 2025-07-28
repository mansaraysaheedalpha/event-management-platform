import { Prisma } from '@prisma/client';
import { IsString, IsDate, IsEnum, IsObject } from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty } from '@nestjs/swagger';

export enum SyncAction {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
  DELETE = 'DELETE',
}

export class SyncLogDto {
  @ApiProperty()
  @IsString()
  id: string;

  @ApiProperty({ type: String, format: 'date-time' })
  @Type(() => Date) // ensures ISO-string → Date conversion
  @IsDate()
  timestamp: Date;

  @ApiProperty()
  @IsString()
  resource: string;

  @ApiProperty({ enum: SyncAction })
  @IsEnum(SyncAction)
  action: SyncAction;

  @ApiProperty({ type: 'object', additionalProperties: true })
  @IsObject()
  payload: Prisma.JsonValue;
}
