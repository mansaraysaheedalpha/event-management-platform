// src/networking/retention/retention.controller.ts
import {
  Controller,
  Post,
  Param,
  UseGuards,
  HttpCode,
  HttpStatus,
  BadRequestException,
} from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { JwtAuthGuard } from 'src/common/guards/jwt-auth.guard';
import { RolesGuard } from 'src/common/guards/roles.guard';
import { RestThrottlerGuard } from 'src/common/guards/rest-throttler.guard';
import { Roles } from 'src/common/decorators/roles.decorator';
import { RetentionService } from './retention.service';

// Valid job names for type safety
const VALID_JOB_NAMES = ['followUpReminders', 'staleNudges', 'weeklyDigest'] as const;
type JobName = (typeof VALID_JOB_NAMES)[number];

function isValidJobName(name: string): name is JobName {
  return VALID_JOB_NAMES.includes(name as JobName);
}

@Controller('networking/retention')
@UseGuards(JwtAuthGuard, RolesGuard, RestThrottlerGuard)
export class RetentionController {
  constructor(private readonly retentionService: RetentionService) {}

  /**
   * Manually trigger a retention job (admin only).
   * Useful for testing and debugging.
   * Rate limited to prevent abuse: 5 requests per hour.
   */
  @Post('trigger/:jobName')
  @Roles('ADMIN', 'SUPER_ADMIN')
  @Throttle({ default: { limit: 5, ttl: 3600000 } }) // 5 per hour
  @HttpCode(HttpStatus.OK)
  async triggerJob(@Param('jobName') jobName: string) {
    // Validate job name to prevent injection
    if (!isValidJobName(jobName)) {
      throw new BadRequestException(
        `Invalid job name. Valid options: ${VALID_JOB_NAMES.join(', ')}`,
      );
    }

    return this.retentionService.triggerJob(jobName);
  }
}
