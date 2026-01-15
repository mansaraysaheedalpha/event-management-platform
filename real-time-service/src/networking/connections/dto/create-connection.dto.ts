//src/networking/connections/dto/create-connection.dto.ts
import { IsString, IsOptional, IsEnum } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { ConnectionType } from '@prisma/client';

export class CreateConnectionDto {
  @ApiProperty({ description: 'ID of the first user in the connection' })
  @IsString()
  userAId: string;

  @ApiProperty({ description: 'ID of the second user in the connection' })
  @IsString()
  userBId: string;

  @ApiProperty({ description: 'Event ID where the connection was made' })
  @IsString()
  eventId: string;

  @ApiPropertyOptional({
    description: 'Type of connection',
    enum: ConnectionType,
    example: 'PROXIMITY_PING',
  })
  @IsOptional()
  @IsEnum(ConnectionType)
  connectionType?: ConnectionType;

  @ApiPropertyOptional({ description: 'Initial message exchanged during connection' })
  @IsOptional()
  @IsString()
  initialMessage?: string;
}
