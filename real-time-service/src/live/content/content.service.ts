import {
  BadRequestException,
  ConflictException,
  Inject,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/shared.module';
import { Redis } from 'ioredis';
import { ContentControlDto } from './dto/content-control.dto';
import { PresentationState } from 'src/common/interfaces/presentation-state.interface';

/**
 * Service to manage live presentation control states
 *
 * Usage:
 *  - Call `controlPresentation` to update the presentation state
 *  - Call `getPresentationState` to fetch current state for a session
 */
@Injectable()
export class ContentService {
  private readonly logger = new Logger(ContentService.name);
  private readonly STATE_TTL = 3 * 60 * 60; // Keep state for 3 hours

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Generates Redis key for a given session.
   *
   * @param sessionId - The session identifier.
   * @returns Redis cache key string.
   */
  private getRedisKey(sessionId: string): string {
    return `presentation:state:${sessionId}`;
  }

  /**
   * Fetches the current state of a presentation from Redis.
   *
   * @param sessionId - The ID of the session.
   * @returns The current presentation state or null if none exists.
   */
  async getPresentationState(
    sessionId: string,
  ): Promise<PresentationState | null> {
    const stateJson = await this.redis.get(this.getRedisKey(sessionId));
    return stateJson ? (JSON.parse(stateJson) as PresentationState) : null;
  }

  /**
   * Handles presentation control actions (start, next slide, etc).
   * Uses idempotency key to prevent duplicate processing.
   *
   * @param sessionId - The session to control.
   * @param dto - Control action data.
   * @returns The updated presentation state.
   */
  async controlPresentation(sessionId: string, dto: ContentControlDto) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate action request.');
    }

    const redisKey = this.getRedisKey(sessionId);
    let currentState = await this.getPresentationState(sessionId);

    // Handle starting the presentation
    if (dto.action === 'START') {
      if (currentState?.isActive) return currentState; // Already started

      const presentation = await this.prisma.presentation.findUnique({
        where: { sessionId },
      });

      if (!presentation) {
        throw new NotFoundException(
          `No presentation found for session ${sessionId}.`,
        );
      }

      currentState = {
        currentSlide: 0,
        totalSlides: presentation.slideUrls.length,
        isActive: true,
        slideUrls: presentation.slideUrls,
      };
    }

    // Ensure presentation is active for other commands
    if (!currentState || !currentState.isActive) {
      throw new BadRequestException('Presentation is not active.');
    }

    // Handle slide navigation
    switch (dto.action) {
      case 'NEXT_SLIDE':
        currentState.currentSlide = Math.min(
          currentState.currentSlide + 1,
          currentState.totalSlides - 1,
        );
        break;
      case 'PREV_SLIDE':
        currentState.currentSlide = Math.max(currentState.currentSlide - 1, 0);
        break;
      case 'GO_TO_SLIDE':
        if (dto.slideNumber === undefined) {
          throw new BadRequestException(
            'slideNumber is required for GO_TO_SLIDE action.',
          );
        }
        currentState.currentSlide = Math.max(
          0,
          Math.min(dto.slideNumber, currentState.totalSlides - 1),
        );
        break;
      case 'END':
        currentState.isActive = false;
        break;
    }

    // Save the new state back to Redis
    await this.redis.set(
      redisKey,
      JSON.stringify(currentState),
      'EX',
      this.STATE_TTL,
    );

    return currentState;
  }
}
