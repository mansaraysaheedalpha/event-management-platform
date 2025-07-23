import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
} from '@nestjs/websockets';
import { ForbiddenException, Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ValidateTicketDto } from './dto/validate-ticket.dto';
import { ValidationService } from './validation.service';

/**
 * Gateway responsible for validating attendee tickets in real-time
 * via WebSocket. This is used by event staff during check-in.
 *
 * Usage (client-side emit):
 * socket.emit('ticket.validate', {
 *   ticketId: 'abc123',
 *   attendeeId: 'user456',
 * });
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ValidationGateway {
  private readonly logger = new Logger(ValidationGateway.name);

  constructor(private readonly validationService: ValidationService) {}

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
  ): Promise<any> {
    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };

    const requiredPermission = 'event:validate_tickets';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to validate tickets.',
      );
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
