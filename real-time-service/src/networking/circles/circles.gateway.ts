//src/networking/circles/circles.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { CirclesService } from './circles.service';
import { CreateCircleDto } from './dto/create-circle.dto';
import { JoinCircleDto } from './dto/join-circle.dto';
import { LeaveCircleDto } from './dto/leave-circle.dto';
import { CloseCircleDto } from './dto/close-circle.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class CirclesGateway {
  private readonly logger = new Logger(CirclesGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly circlesService: CirclesService) {}

  /**
   * Handles a user's request to create a new Conversation Circle.
   */
  @SubscribeMessage('circle.create')
  async handleCreateCircle(
    @MessageBody() dto: CreateCircleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    // In a future version, you might add a specific permission for this.
    // For now, we'll assume any authenticated user can create a circle.

    try {
      const newCircle = await this.circlesService.createCircle(
        user.sub,
        sessionId,
        dto,
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'circle.opened';

      // Broadcast the new circle to everyone in the session
      this.server.to(publicRoom).emit(eventName, newCircle);
      if (newCircle) {
        this.logger.log(
          `Broadcasted new circle ${newCircle.id} to room ${publicRoom}`,
        );
      } else {
        this.logger.warn(
          `Attempted to broadcast a null circle to room ${publicRoom}`,
        );
      }

      return { success: true, circleId: newCircle ? newCircle.id : null };
    } catch (error) {
      this.logger.error(
        `Failed to create circle for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a user's request to join a Conversation Circle.
   */
  @SubscribeMessage('circle.join')
  async handleJoinCircle(
    @MessageBody() dto: JoinCircleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedRoster = await this.circlesService.joinCircle(
        user.sub,
        dto.circleId,
      );
      this.server
        .to(`session:${sessionId}`)
        .emit('circle.roster.updated', updatedRoster);
      return { success: true, circleId: dto.circleId };
    } catch (error) {
      this.logger.error(
        `Failed to join circle ${dto.circleId} for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a user's request to leave a Conversation Circle.
   */
  @SubscribeMessage('circle.leave')
  async handleLeaveCircle(
    @MessageBody() dto: LeaveCircleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedRoster = await this.circlesService.leaveCircle(
        user.sub,
        dto.circleId,
      );
      this.server
        .to(`session:${sessionId}`)
        .emit('circle.roster.updated', updatedRoster);
      return { success: true, circleId: dto.circleId };
    } catch (error) {
      this.logger.error(
        `Failed to leave circle ${dto.circleId} for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a moderator's request to close a Conversation Circle.
   */
  @SubscribeMessage('circle.close')
  async handleCloseCircle(
    @MessageBody() dto: CloseCircleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const closedCircle = await this.circlesService.closeCircle(
        dto.circleId,
        user.sub,
        user.permissions ?? [],
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'circle.closed';

      this.server.to(publicRoom).emit(eventName, { circleId: closedCircle.id });
      this.logger.log(`Broadcasted close event for circle ${closedCircle.id}`);

      return { success: true, circleId: closedCircle.id };
    } catch (error) {
      this.logger.error(
        `Failed to close circle for admin ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
