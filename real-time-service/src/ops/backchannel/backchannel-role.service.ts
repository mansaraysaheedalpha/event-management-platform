//src/ops/backchannel/backchannel-role.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';
import { TargetableRole } from './dto/send-backchannel-message.dto';
import { PrismaService } from 'src/prisma.service';

/**
 * Permissions that qualify a user as a MODERATOR in the backchannel.
 * These are users who can moderate Q&A, chat, or manage content.
 */
const MODERATOR_PERMISSIONS = [
  'qna:moderate',
  'chat:moderate',
  'chat:delete:any',
];

/**
 * Permissions that qualify a user as STAFF in the backchannel.
 * These are organization administrators and owners.
 */
const STAFF_PERMISSIONS = [
  'backchannel:join',
  'content:manage',
  'event:manage',
];

interface SpeakerCheckResponse {
  is_speaker: boolean;
  speaker_id?: string;
}

/**
 * Service responsible for determining a user's roles within the backchannel context.
 *
 * Enterprise Design:
 * - STAFF: Organization administrators (OWNER/ADMIN roles)
 * - MODERATOR: Users with moderation permissions (qna:moderate, chat:moderate)
 * - SPEAKER: Users assigned as speakers for the specific session
 *
 * A user can have multiple roles simultaneously (e.g., STAFF + SPEAKER).
 */
@Injectable()
export class BackchannelRoleService {
  private readonly logger = new Logger(BackchannelRoleService.name);
  private readonly eventServiceUrl: string;
  private readonly internalApiKey: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    private readonly prisma: PrismaService,
  ) {
    this.eventServiceUrl = this.configService.get<string>(
      'EVENT_LIFECYCLE_SERVICE_URL',
      'http://localhost:8000',
    );
    this.internalApiKey = this.configService.get<string>('INTERNAL_API_KEY', '');
  }

  /**
   * Determines all backchannel roles for a user based on their permissions
   * and session-specific speaker assignment.
   *
   * @param userId - The user's ID
   * @param sessionId - The session ID for speaker lookup
   * @param permissions - User's permissions array from JWT
   * @returns Array of TargetableRole values the user belongs to
   */
  async getUserBackchannelRoles(
    userId: string,
    sessionId: string,
    permissions: string[] = [],
  ): Promise<TargetableRole[]> {
    const roles: TargetableRole[] = [];

    // Check for STAFF role based on permissions
    if (this.hasAnyPermission(permissions, STAFF_PERMISSIONS)) {
      roles.push(TargetableRole.STAFF);
    }

    // Check for MODERATOR role based on permissions
    if (this.hasAnyPermission(permissions, MODERATOR_PERMISSIONS)) {
      roles.push(TargetableRole.MODERATOR);
    }

    // Check for SPEAKER role by querying session-speaker assignment
    const isSpeaker = await this.checkIfUserIsSpeaker(userId, sessionId);
    if (isSpeaker) {
      roles.push(TargetableRole.SPEAKER);
    }

    this.logger.debug(
      `User ${userId} backchannel roles for session ${sessionId}: [${roles.join(', ')}]`,
    );

    return roles;
  }

  /**
   * Checks if user has any of the specified permissions.
   */
  private hasAnyPermission(
    userPermissions: string[],
    requiredPermissions: string[],
  ): boolean {
    return requiredPermissions.some((p) => userPermissions.includes(p));
  }

  /**
   * Checks if a user is assigned as a speaker for the given session.
   *
   * This queries the event-lifecycle-service to check the session-speaker
   * association. Falls back gracefully if the service is unavailable.
   *
   * @param userId - The user's ID
   * @param sessionId - The session ID to check
   * @returns true if user is a speaker for this session
   */
  private async checkIfUserIsSpeaker(
    userId: string,
    sessionId: string,
  ): Promise<boolean> {
    // First, try to get session info from local database to find the event
    try {
      const chatSession = await this.prisma.chatSession.findUnique({
        where: { id: sessionId },
        select: { eventId: true },
      });

      if (!chatSession?.eventId) {
        this.logger.debug(`No event found for session ${sessionId}`);
        return false;
      }

      // Query event-lifecycle-service to check if user is a speaker
      const baseUrl = this.eventServiceUrl.replace('/graphql', '');
      const response = await firstValueFrom(
        this.httpService.get<SpeakerCheckResponse>(
          `${baseUrl}/api/v1/internal/sessions/${sessionId}/speakers/${userId}/check`,
          {
            headers: {
              'X-Internal-Api-Key': this.internalApiKey,
            },
            timeout: 2000, // Short timeout to prevent blocking
          },
        ),
      );

      return response.data?.is_speaker ?? false;
    } catch (error: any) {
      // Log but don't fail - speaker check is optional enhancement
      if (error.response?.status === 404) {
        // User is not a speaker - this is expected for most users
        return false;
      }

      this.logger.debug(
        `Speaker check unavailable for user ${userId}, session ${sessionId}: ${error.message}`,
      );
      return false;
    }
  }

  /**
   * Generates the Socket.IO room names for a user's backchannel roles.
   *
   * @param sessionId - The session ID
   * @param roles - Array of roles the user belongs to
   * @returns Array of room names to join
   */
  getRoomNamesForRoles(sessionId: string, roles: TargetableRole[]): string[] {
    return roles.map((role) => `backchannel:${sessionId}:role:${role}`);
  }
}
