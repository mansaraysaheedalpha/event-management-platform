//src/shared/services/user-validation.service.ts
import {
  Injectable,
  Logger,
  UnauthorizedException,
  OnModuleInit,
} from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

interface UserStatusResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

/**
 * UserValidationService validates user status against user-org-service.
 * Ensures users are still active/exist before allowing WebSocket connections.
 */
@Injectable()
export class UserValidationService implements OnModuleInit {
  private readonly logger = new Logger(UserValidationService.name);
  private readonly userOrgServiceUrl: string;
  private readonly internalApiKey: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.userOrgServiceUrl = this.configService.get<string>(
      'USER_ORG_SERVICE_URL',
      'http://localhost:3001',
    );
    this.internalApiKey =
      this.configService.getOrThrow<string>('INTERNAL_API_KEY');
  }

  onModuleInit() {
    this.logger.log(
      'UserValidationService initialized with INTERNAL_API_KEY configured',
    );
  }

  /**
   * Validates that a user exists and is active in user-org-service.
   * @param userId - The ID of the user to validate.
   * @returns User data if valid.
   * @throws UnauthorizedException if user doesn't exist or is inactive.
   */
  async validateUserStatus(userId: string): Promise<UserStatusResponse> {
    // Remove /graphql suffix if present (URL might be configured for GraphQL)
    const baseUrl = this.userOrgServiceUrl.replace('/graphql', '');

    try {
      const response = await firstValueFrom(
        this.httpService.get<UserStatusResponse>(
          `${baseUrl}/internal/users/${userId}`,
          {
            headers: {
              'X-Internal-Api-Key': this.internalApiKey,
            },
            timeout: 3000, // 3 second timeout for connection validation
          },
        ),
      );

      this.logger.debug(`User ${userId} validated successfully`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        this.logger.warn(`User ${userId} not found in user-org-service`);
        throw new UnauthorizedException(
          'User account no longer exists or has been deactivated.',
        );
      }

      if (error.response?.status === 401 || error.response?.status === 403) {
        this.logger.error(
          `Authentication failed when validating user ${userId}. Check INTERNAL_API_KEY.`,
        );
        // Don't block connection if internal auth fails - log and allow
        // This prevents service outage if API key misconfigured
        throw new UnauthorizedException(
          'Unable to verify user status. Please try again.',
        );
      }

      // For network errors or timeouts, log but allow connection
      // This prevents real-time service from being blocked by user-org-service downtime
      this.logger.error(
        `Failed to validate user ${userId}: ${error.message}. Allowing connection with degraded validation.`,
      );

      // Return a minimal response to allow connection to proceed
      // In production, you might want to fail closed instead
      return { id: userId, email: '', first_name: '', last_name: '' };
    }
  }

  /**
   * Checks if a user exists without throwing.
   * @param userId - The ID of the user to check.
   * @returns True if user exists, false otherwise.
   */
  async isUserActive(userId: string): Promise<boolean> {
    try {
      await this.validateUserStatus(userId);
      return true;
    } catch {
      return false;
    }
  }
}
