//src/live/validation/validation.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
} from '@nestjs/websockets';
import { ForbiddenException, Inject, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { ValidateTicketDto } from './dto/validate-ticket.dto';
import { ValidationService } from './validation.service';
import { ValidationResultDto } from './dto/validation-result.dto';

type ValidationResponse =
  | { success: true; event: 'validation.result'; data: ValidationResultDto }
  | { success: false; error: string };
/**
 * Gateway responsible for validating attendee tickets in real-time
 * via WebSocket. This is used by event staff during check-in.
 *
 * @example
 * ```typescript
 * socket.emit('ticket.validate', {
 *   ticketId: 'abc123',
 *   attendeeId: 'user456',
 * });
 * ```
 *
 * @see https://docs.nestjs.com/websockets/gateways
 */
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class ValidationGateway {
  private readonly logger = new Logger(ValidationGateway.name);

  constructor(
    private readonly validationService: ValidationService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Handles a WebSocket ticket validation request from staff.
   *
   * @param dto Ticket validation payload.
   * @param client The connected authenticated socket client.
   * @returns A success/failure response containing validation result or error.
   */
  @SubscribeMessage('ticket.validate')
  async handleValidateTicket(
    @MessageBody() dto: ValidateTicketDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<ValidationResponse> {
    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };

    const requiredPermission = 'event:validate_tickets';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to validate tickets.',
      );
    }

    // Verify user has access to this specific event (not just the permission globally)
    const userOrgId = user.orgId;
    if (!userOrgId) {
      return { success: false, error: 'Organization context required' };
    }

    const eventBelongsToOrg = await this.redis.sismember(
      `org:active_events:${userOrgId}`,
      eventId,
    );
    if (!eventBelongsToOrg) {
      this.logger.warn(
        `Staff ${user.sub} (org: ${userOrgId}) attempted to validate tickets for event ${eventId} outside their organization`,
      );
      return {
        success: false,
        error: 'You do not have access to this event',
      };
    }

    try {
      const result = await this.validationService.validateTicket(eventId, dto);
      return { success: true, event: 'validation.result', data: result };
    } catch (error) {
      this.logger.error(
        `Failed to validate ticket for staff ${user.sub}`,
        error,
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
