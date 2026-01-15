//src/networking/follow-up/dto/schedule-follow-ups.dto.ts
import { IsString, IsOptional, IsDateString } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ScheduleFollowUpsDto {
  @ApiProperty({ description: 'Event ID to schedule follow-ups for' })
  @IsString()
  eventId: string;

  @ApiPropertyOptional({
    description: 'When to send follow-up emails (defaults to 24 hours from now)',
    example: '2026-01-16T10:00:00Z',
  })
  @IsOptional()
  @IsDateString()
  scheduledFor?: string;
}
