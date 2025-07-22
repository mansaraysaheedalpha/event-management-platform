import { HttpService } from '@nestjs/axios';
import { ConflictException, Injectable, Logger } from '@nestjs/common';
import { firstValueFrom } from 'rxjs';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { ValidateTicketDto } from './dto/validate-ticket.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ValidationResultDto } from './dto/validation-result.dto';

@Injectable()
export class ValidationService {
  private readonly logger = new Logger(ValidationService.name);

  constructor(
    private readonly httpService: HttpService,
    private readonly idempotencyService: IdempotencyService,
    private readonly publisherService: PublisherService,
  ) {}

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
      // 1. Call the Event Lifecycle service to validate the ticket
      const eventServiceUrl =
        process.env.EVENT_SERVICE_URL || 'http://localhost:8000';
      const response = await firstValueFrom(
        this.httpService.post<ValidationResultDto>(
          `${eventServiceUrl}/internal/tickets/validate`,
          { eventId, ...dto }, // Send eventId along with ticket code
          { headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY } },
        ),
      );

      const validationResult = response.data;

      // 2. If validation was successful, publish an event for the dashboard's live check-in feed
      if (validationResult?.isValid) {
        const analyticsPayload = {
          type: 'CHECK_IN_PROCESSED',
          eventId: eventId,
          checkInData: validationResult.user,
        };
        void this.publisherService.publish(
          'platform.analytics.check-in.v1',
          analyticsPayload,
        );
      }

      // 3. Return the result to the gateway
      return validationResult;
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(`Ticket validation failed: ${errorMessage}`);
      // Re-throw the error to be handled by the gateway
      throw error;
    }
  }
}
