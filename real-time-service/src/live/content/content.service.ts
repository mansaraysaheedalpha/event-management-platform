//src/content/content.service.ts
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { ConfigService } from '@nestjs/config';
import {
  BadRequestException,
  ConflictException,
  Inject,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { Redis } from 'ioredis';
import { ContentControlDto } from './dto/content-control.dto';
import { PresentationStateDto } from './dto/presentation-state.dto';
import { DropContentDto } from './dto/drop-content.dto';

/**
 * Service to manage live presentation control states
 *
 * Usage:
 *  - Call `controlPresentation` to update the presentation state
 *  - Call `getPresentationState` to fetch current state for a session
 */

interface DroppedContentPayload {
  title: string;
  description?: string;
  contentType: DropContentDto['contentType'];
  contentUrl: string;
  droppedBy: { id: string; name: string };
  timestamp: string;
}

@Injectable()
export class ContentService {
  private readonly logger = new Logger(ContentService.name);
  private readonly STATE_TTL = 3 * 60 * 60; // Keep state for 3 hours

  constructor(
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly httpService: HttpService, // INJECT HttpService
    private readonly configService: ConfigService, // INJECT ConfigService
  ) {}

  /**
   * @internal
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
  ): Promise<PresentationStateDto | null> {
    const stateJson = await this.redis.get(this.getRedisKey(sessionId));
    if (!stateJson) return null;
    try {
      return JSON.parse(stateJson) as PresentationStateDto;
    } catch (err) {
      this.logger.warn(
        `Failed to parse presentation state for session ${sessionId}: ${err}`,
      );
      return null;
    }
  }

  /**
   * Handles presentation control actions (start, next slide, etc).
   * Uses idempotency key to prevent duplicate processing.
   *
   * @param sessionId - The session to control.
   * @param dto - Control action data.
   * @returns The updated presentation state.
   * @throws ConflictException if a duplicate action request is detected.
   * @throws NotFoundException if no presentation is found for the session.
   * @throws BadRequestException if the presentation is not active or required parameters are missing.
   */
  async controlPresentation(
    sessionId: string,
    dto: ContentControlDto,
  ): Promise<PresentationStateDto> {
    const redisKey = this.getRedisKey(sessionId);
    let currentState = await this.getPresentationState(sessionId);

    // For START action, check if already active BEFORE consuming idempotency key
    // This allows clicking "Present Live" multiple times without error
    if (dto.action === 'START' && currentState?.isActive) {
      this.logger.log(`Presentation already active for session ${sessionId}, returning current state`);
      return currentState;
    }

    // Idempotency check for all other cases
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate action request.');
    }

    if (dto.action === 'START') {

      try {
        // Use EVENT_LIFECYCLE_SERVICE_URL for both internal and external calls
        // On Render, services can communicate via their public URLs
        const eventServiceUrl = this.configService.getOrThrow<string>(
          'EVENT_LIFECYCLE_SERVICE_URL',
        );
        const internalApiKey =
          this.configService.getOrThrow<string>('INTERNAL_API_KEY');

        // Step 1: Get session details to find orgId and eventId
        const detailsUrl = `${eventServiceUrl}/api/v1/internal/sessions/${sessionId}/details`;
        const { data: sessionDetails } = await firstValueFrom(
          this.httpService.get(detailsUrl, {
            headers: { 'X-Internal-Api-Key': internalApiKey },
          }),
        );

        if (!sessionDetails) {
          throw new NotFoundException(
            `Session details not found for ID: ${sessionId}`,
          );
        }

        // Step 2: Use details to get the presentation data via the internal-friendly endpoint
        const presentationUrl = `${eventServiceUrl}/api/v1/organizations/${sessionDetails.organization_id}/events/${sessionDetails.event_id}/sessions/${sessionId}/presentation`;
        const { data: presentation } = await firstValueFrom(
          this.httpService.get(presentationUrl, {
            headers: { 'X-Internal-Api-Key': internalApiKey },
          }),
        );

        currentState = {
          currentSlide: 1,  // 1-indexed for frontend display
          totalSlides: presentation.slide_urls.length,
          isActive: true,
          slideUrls: presentation.slide_urls,
        };
      } catch (error) {
        this.logger.error(
          `Failed to fetch presentation data for session ${sessionId}:`,
          error.stack,
        );
        if (error.response?.status === 404) {
          throw new NotFoundException(
            `No presentation found for session ${sessionId}.`,
          );
        }
        throw new BadRequestException('Could not start presentation.');
      }
    }

    if (!currentState || !currentState.isActive) {
      throw new BadRequestException('Presentation is not active.');
    }

    // Handle slide navigation logic (1-indexed: slides go from 1 to totalSlides)
    switch (dto.action) {
      case 'NEXT_SLIDE':
        currentState.currentSlide = Math.min(
          currentState.currentSlide + 1,
          currentState.totalSlides,  // Max is totalSlides (1-indexed)
        );
        break;
      case 'PREV_SLIDE':
        currentState.currentSlide = Math.max(currentState.currentSlide - 1, 1);  // Min is 1 (1-indexed)
        break;
      case 'GO_TO_SLIDE': {
        // Support both slideNumber and targetSlide for frontend compatibility
        const targetSlide = dto.slideNumber ?? dto.targetSlide;
        if (targetSlide === undefined) {
          throw new BadRequestException(
            'slideNumber or targetSlide is required for GO_TO_SLIDE action.',
          );
        }
        currentState.currentSlide = Math.max(
          1,  // Min is 1 (1-indexed)
          Math.min(targetSlide, currentState.totalSlides),  // Max is totalSlides
        );
        break;
      }
      case 'STOP':
      case 'END':
        currentState.isActive = false;
        break;
    }

    await this.redis.set(
      redisKey,
      JSON.stringify(currentState),
      'EX',
      this.STATE_TTL,
    );

    return currentState;
  }

  /**
   * Logs the content drop event to the database and prepares the payload for broadcasting.
   */
  async handleContentDrop(
    dto: DropContentDto,
    dropper: { id: string; name: string },
    sessionId: string,
  ): Promise<DroppedContentPayload> {
    this.logger.log(`User ${dropper.id} dropping content: ${dto.title}`);

    // This function doesn't exist in the PrismaService you provided,
    // so I am assuming it's a placeholder for now.
    // If you have a contentDropLog model in your Prisma schema, this will work.
    // await this.prisma.contentDropLog.create({
    //   data: {
    //     dropperId: dropper.id,
    //     sessionId,
    //     title: dto.title,
    //     description: dto.description,
    //     contentType: dto.contentType,
    //     contentUrl: dto.contentUrl,
    //   },
    // });

    return {
      ...dto,
      droppedBy: dropper,
      timestamp: new Date().toISOString(),
    };
  }
}
