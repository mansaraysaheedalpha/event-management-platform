//src/live/validation/validation.service.ts
const ANALYTICS_CHECKIN_TOPIC = 'platform.analytics.check-in.v1';
import { HttpService } from '@nestjs/axios';
import { ConflictException, Injectable, Logger } from '@nestjs/common';
import { firstValueFrom } from 'rxjs';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { ValidateTicketDto } from './dto/validate-ticket.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ValidationResultDto } from './dto/validation-result.dto';

/**
 * Service that handles business logic for validating event tickets.
 * It ensures idempotency, communicates with the Event Lifecycle API,
 * and publishes analytics events for real-time check-in dashboards.
 *
 * @example
 * // Typical usage in a NestJS service or controller:
 * import { ValidationService } from './validation.service';
 *
 * @Injectable()
 * export class SomeController {
 *   constructor(private readonly validationService: ValidationService) {}
 *
 *   async validate(eventId: string, dto: ValidateTicketDto) {
 *     return await this.validationService.validateTicket(eventId, dto);
 *   }
 * }
 */
@Injectable()
export class ValidationService {
  private readonly logger = new Logger(ValidationService.name);

  constructor(
    private readonly httpService: HttpService,
    private readonly idempotencyService: IdempotencyService,
    private readonly publisherService: PublisherService,
  ) {}

  /**
   * Validates a ticket for a specific event.
   * - Checks idempotency to prevent duplicate validation.
   * - Calls Event Lifecycle service for actual validation.
   * - Publishes real-time check-in data if valid.
   *
   * @param eventId The event ID tied to the validation context.
   * @param dto The ticket validation payload (ticket code, idempotency key, etc.).
   * @returns The result of the validation (valid/invalid, user info, etc.).
   * @throws ConflictException (HTTP 409) if the same idempotencyKey has been processed.
   * @throws BadRequestException (HTTP 400) for invalid payload or ticket code.
   * @throws Network timeout or connection errors (HTTP 504/502) if the Event Lifecycle service is unreachable.
   * @throws Other errors returned by the Event Lifecycle service, mapped to their respective HTTP status codes.
   */
  async validateTicket(
    eventId: string,
    dto: ValidateTicketDto,
  ): Promise<ValidationResultDto> {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'This ticket validation has already been processed.',
      );
    }

    try {
      const eventServiceUrl =
        process.env.EVENT_SERVICE_URL || 'http://localhost:8000';

      const response = await firstValueFrom(
        this.httpService.post<ValidationResultDto>(
          `${eventServiceUrl}/internal/tickets/validate`,
          // Ensure the explicit eventId wins in case dto contains one.
          { ...dto, eventId },
          {
            headers: {
              // Only attach the header when the key is configured.
              ...(process.env.INTERNAL_API_KEY
                ? { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY }
                : {}),
            },
          },
        ),
      );

      const validationResult = response.data;

      if (validationResult?.isValid) {
        const analyticsPayload = {
          type: 'CHECK_IN_PROCESSED',
          eventId: eventId,
          checkInData: validationResult.user,
        };

        void this.publisherService.publish(
          ANALYTICS_CHECKIN_TOPIC,
          analyticsPayload,
        );
      }

      return validationResult;
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(`Ticket validation failed: ${errorMessage}`);
      throw error;
    }
  }
}
