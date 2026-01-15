//src/networking/follow-up/dto/send-follow-up.dto.ts
import { IsString, IsOptional, MinLength, MaxLength } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class SendFollowUpDto {
  @ApiProperty({
    description: 'Follow-up message content',
    minLength: 1,
    maxLength: 2000,
    example: 'Hi! Great meeting you at the conference. Would love to continue our conversation.',
  })
  @IsString()
  @MinLength(1)
  @MaxLength(2000)
  message: string;

  @ApiPropertyOptional({
    description: 'Custom email subject (optional)',
    maxLength: 200,
    example: 'Following up from TechConf 2026',
  })
  @IsOptional()
  @IsString()
  @MaxLength(200)
  subject?: string;
}
