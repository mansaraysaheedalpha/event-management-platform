//src/shared/services/event-registration-validation.service.ts
import {
  Injectable,
  Logger,
  ForbiddenException,
  OnModuleInit,
} from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

interface RegistrationResponse {
  id: string;
  event_id: string;
  user_id: string;
  status: string;
  ticket_code: string;
}

/**
 * EventRegistrationValidationService validates user event registrations
 * against the event-lifecycle-service.
 * Ensures users are registered for events before allowing access to event resources.
 */
@Injectable()
export class EventRegistrationValidationService implements OnModuleInit {
  private readonly logger = new Logger(EventRegistrationValidationService.name);
  private readonly eventServiceUrl: string;
  private readonly internalApiKey: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.eventServiceUrl = this.configService.get<string>(
      'EVENT_LIFECYCLE_SERVICE_URL',
      'http://localhost:8000',
    );
    this.internalApiKey =
      this.configService.getOrThrow<string>('INTERNAL_API_KEY');
  }

  onModuleInit() {
    this.logger.log(
      'EventRegistrationValidationService initialized with INTERNAL_API_KEY configured',
    );
  }

  /**
   * Validates that a user is registered for a specific event.
   * @param userId - The ID of the user to validate.
   * @param eventId - The ID of the event to check registration for.
   * @returns Registration data if valid.
   * @throws ForbiddenException if user is not registered for the event.
   */
  async validateEventRegistration(
    userId: string,
    eventId: string,
  ): Promise<RegistrationResponse> {
    // Remove /graphql suffix if present (URL might be configured for GraphQL)
    const baseUrl = this.eventServiceUrl.replace('/graphql', '');

    try {
      const response = await firstValueFrom(
        this.httpService.get<RegistrationResponse>(
          `${baseUrl}/api/v1/internal/events/${eventId}/registrations/${userId}`,
          {
            headers: {
              'X-Internal-Api-Key': this.internalApiKey,
            },
            timeout: 3000,
          },
        ),
      );

      this.logger.debug(
        `User ${userId} registration for event ${eventId} validated successfully`,
      );
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        this.logger.warn(
          `User ${userId} is not registered for event ${eventId}`,
        );
        throw new ForbiddenException(
          'You are not registered for this event.',
        );
      }

      if (error.response?.status === 401 || error.response?.status === 403) {
        this.logger.error(
          `Authentication failed when validating registration for user ${userId}. Check INTERNAL_API_KEY.`,
        );
        throw new ForbiddenException(
          'Unable to verify event registration. Please try again.',
        );
      }

      // For network errors or timeouts, log but allow connection
      // This prevents real-time service from being blocked by event-lifecycle-service downtime
      this.logger.error(
        `Failed to validate registration for user ${userId} on event ${eventId}: ${error.message}. Allowing with degraded validation.`,
      );

      // Return minimal response to allow connection to proceed
      return {
        id: '',
        event_id: eventId,
        user_id: userId,
        status: 'unknown',
        ticket_code: '',
      };
    }
  }

  /**
   * Checks if a user is registered for an event without throwing.
   * @param userId - The ID of the user to check.
   * @param eventId - The ID of the event to check.
   * @returns True if user is registered, false otherwise.
   */
  async isUserRegistered(userId: string, eventId: string): Promise<boolean> {
    try {
      const result = await this.validateEventRegistration(userId, eventId);
      // If we got a degraded response (empty id), treat as not registered for strict checks
      return result.id !== '';
    } catch {
      return false;
    }
  }
}
