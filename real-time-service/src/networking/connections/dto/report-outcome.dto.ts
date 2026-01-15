//src/networking/connections/dto/report-outcome.dto.ts
import { IsEnum, IsOptional, IsString, IsBoolean, IsDateString } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { OutcomeType } from '@prisma/client';

export class ReportOutcomeDto {
  @ApiProperty({
    description: 'Type of outcome from the connection',
    enum: OutcomeType,
    example: 'MEETING_HELD',
  })
  @IsEnum(OutcomeType)
  outcomeType: OutcomeType;

  @ApiPropertyOptional({ description: 'Additional notes about the outcome' })
  @IsOptional()
  @IsString()
  outcomeNotes?: string;

  @ApiPropertyOptional({ description: 'Whether a meeting was scheduled' })
  @IsOptional()
  @IsBoolean()
  meetingScheduled?: boolean;

  @ApiPropertyOptional({
    description: 'Date of the scheduled meeting',
    example: '2026-02-01T10:00:00Z',
  })
  @IsOptional()
  @IsDateString()
  meetingDate?: string;
}
