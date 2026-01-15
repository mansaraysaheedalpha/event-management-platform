//src/networking/huddles/huddles.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
  WsException,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger, UseGuards } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { EventRegistrationValidationService } from 'src/shared/services/event-registration-validation.service';
import { WsThrottlerGuard } from 'src/common/guards/ws-throttler.guard';
import { HuddlesService } from './huddles.service';
import { CreateHuddleDto } from './dto/create-huddle.dto';
import { JoinHuddleDto } from './dto/join-huddle.dto';
import { LeaveHuddleDto } from './dto/leave-huddle.dto';
import { RespondHuddleDto, HuddleResponseType } from './dto/respond-huddle.dto';
import { InviteToHuddleDto } from './dto/invite-huddle.dto';
import { StartHuddleDto } from './dto/start-huddle.dto';
import { CompleteHuddleDto } from './dto/complete-huddle.dto';
import { CancelHuddleDto } from './dto/cancel-huddle.dto';
import { ListHuddlesDto, MyHuddlesDto } from './dto/list-huddles.dto';

/**
 * Sanitize user input for logging to prevent log injection attacks.
 */
const sanitizeForLog = (input: string | undefined | null, maxLength = 50): string => {
  if (!input) return '[empty]';
  return input
    .replace(/[\r\n]/g, ' ')
    .replace(/[^\x20-\x7E]/g, '')
    .substring(0, maxLength);
};

/**
 * HuddlesGateway handles all WebSocket events for the Facilitated Huddles feature.
 *
 * WebSocket Events - Huddles Namespace (/events)
 *
 * Client -> Server:
 * - 'huddle.create' { CreateHuddleDto } - Create a new huddle
 * - 'huddle.join' { huddleId: string } - Join a huddle room
 * - 'huddle.leave' { huddleId: string } - Leave a huddle
 * - 'huddle.respond' { huddleId: string, response: 'accept'|'decline' } - Respond to invitation
 * - 'huddle.invite' { huddleId: string, userIds: string[] } - Invite users to huddle
 * - 'huddle.start' { huddleId: string } - Start the huddle (creator only)
 * - 'huddle.complete' { huddleId: string } - Complete the huddle (creator only)
 * - 'huddle.cancel' { huddleId: string, reason?: string } - Cancel the huddle
 *
 * Server -> Client:
 * - 'huddle.invitation' HuddleInvitationPayload - New invitation received
 * - 'huddle.participant_joined' { huddleId, userId, userName, totalConfirmed }
 * - 'huddle.participant_left' { huddleId, userId, totalConfirmed }
 * - 'huddle.confirmed' { huddleId } - Minimum participants reached
 * - 'huddle.started' { huddleId } - Huddle has started
 * - 'huddle.cancelled' { huddleId, reason } - Huddle was cancelled
 * - 'huddle.completed' { huddleId } - Huddle ended
 * - 'huddle.response_error' { huddleId, error, huddleFull?, message? }
 */
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
@UseGuards(WsThrottlerGuard)
export class HuddlesGateway {
  private readonly logger = new Logger(HuddlesGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly huddlesService: HuddlesService,
    private readonly eventValidation: EventRegistrationValidationService,
  ) {}

  /**
   * Create a new huddle.
   */
  @SubscribeMessage('huddle.create')
  @Throttle({ default: { limit: 10, ttl: 60000 } }) // 10 huddle creates per minute
  async handleCreateHuddle(
    @MessageBody() dto: CreateHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify user is registered for the event
      await this.eventValidation.validateEventRegistration(user.sub, dto.eventId);

      const huddle = await this.huddlesService.createHuddle(user.sub, dto);

      // Join the huddle room
      await client.join(`huddle:${huddle.id}`);

      // Broadcast new huddle to event room
      this.server.to(`event:${dto.eventId}`).emit('huddle.created', {
        huddleId: huddle.id,
        topic: huddle.topic,
        problemStatement: huddle.problemStatement,
        scheduledAt: huddle.scheduledAt,
        duration: huddle.duration,
        locationName: huddle.locationName,
        maxParticipants: huddle.maxParticipants,
        createdById: user.sub,
      });

      this.logger.log(`Huddle ${huddle.id} created by user ${user.sub}`);
      return { success: true, huddleId: huddle.id };
    } catch (error) {
      this.logger.error(
        `Failed to create huddle for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Join a huddle room to receive updates.
   * Verifies user is invited to the huddle and registered for the event.
   */
  @SubscribeMessage('huddle.join')
  async handleJoinHuddle(
    @MessageBody() dto: JoinHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify user is a participant in this huddle
      const participant = await this.huddlesService.getParticipant(
        dto.huddleId,
        user.sub,
      );

      if (!participant) {
        throw new WsException('Not invited to this huddle');
      }

      // Verify user is registered for the event
      const huddle = await this.huddlesService.getHuddle(dto.huddleId);
      await this.eventValidation.validateEventRegistration(
        user.sub,
        huddle.eventId,
      );

      // Join the huddle room
      await client.join(`huddle:${dto.huddleId}`);

      this.logger.log(`User ${user.sub} joined huddle room ${dto.huddleId}`);
      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to join huddle ${dto.huddleId} for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Respond to a huddle invitation (accept/decline).
   * Rate limited to prevent spam.
   */
  @SubscribeMessage('huddle.respond')
  @Throttle({ default: { limit: 5, ttl: 60000 } }) // 5 responses per minute
  async handleHuddleResponse(
    @MessageBody() dto: RespondHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const result = await this.huddlesService.recordResponse(
        dto.huddleId,
        user.sub,
        dto.response,
      );

      if (!result.success) {
        // Emit error to the client
        client.emit('huddle.response_error', {
          huddleId: dto.huddleId,
          error: result.error,
          huddleFull: result.huddleFull,
          message: result.message,
        });
        return { success: false, error: result.error };
      }

      // If accepted, notify other participants
      if (dto.response === HuddleResponseType.ACCEPT) {
        const huddle = await this.huddlesService.getHuddle(dto.huddleId);
        const acceptedCount = huddle.participants.filter(
          (p) => p.status === 'ACCEPTED',
        ).length;

        // Notify all participants in the huddle room
        this.server.to(`huddle:${dto.huddleId}`).emit('huddle.participant_joined', {
          huddleId: dto.huddleId,
          userId: user.sub,
          totalConfirmed: acceptedCount,
        });

        // Join the huddle room
        await client.join(`huddle:${dto.huddleId}`);

        // Check if huddle is now confirmed
        const confirmed = await this.huddlesService.checkAndConfirmHuddle(
          dto.huddleId,
        );
        if (confirmed) {
          this.server.to(`huddle:${dto.huddleId}`).emit('huddle.confirmed', {
            huddleId: dto.huddleId,
          });
          this.logger.log(`Huddle ${dto.huddleId} is now confirmed`);
        }
      }

      this.logger.log(
        `User ${user.sub} ${dto.response}ed huddle ${dto.huddleId}`,
      );
      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to record response for huddle ${dto.huddleId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Invite users to a huddle.
   * Only participants who are already part of the huddle can invite others.
   */
  @SubscribeMessage('huddle.invite')
  @Throttle({ default: { limit: 10, ttl: 60000 } }) // 10 invite batches per minute
  async handleInviteToHuddle(
    @MessageBody() dto: InviteToHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const result = await this.huddlesService.inviteToHuddle(
        user.sub,
        dto.huddleId,
        dto.userIds,
      );

      // Build invitation payload
      const invitationPayload = await this.huddlesService.buildInvitationPayload(
        dto.huddleId,
      );

      // Send invitation to each newly invited user
      for (const userId of result.invited) {
        this.server.to(`user:${userId}`).emit('huddle.invitation', invitationPayload);
      }

      this.logger.log(
        `User ${user.sub} invited ${result.invited.length} users to huddle ${dto.huddleId}`,
      );
      return {
        success: true,
        invited: result.invited,
        alreadyInvited: result.alreadyInvited,
      };
    } catch (error) {
      this.logger.error(
        `Failed to invite users to huddle ${dto.huddleId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Leave a huddle.
   */
  @SubscribeMessage('huddle.leave')
  async handleLeaveHuddle(
    @MessageBody() dto: LeaveHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      await this.huddlesService.leaveHuddle(dto.huddleId, user.sub);

      // Leave the socket room
      await client.leave(`huddle:${dto.huddleId}`);

      // Get updated count
      const huddle = await this.huddlesService.getHuddle(dto.huddleId);
      const acceptedCount = huddle.participants.filter(
        (p) => p.status === 'ACCEPTED',
      ).length;

      // Notify remaining participants
      this.server.to(`huddle:${dto.huddleId}`).emit('huddle.participant_left', {
        huddleId: dto.huddleId,
        userId: user.sub,
        totalConfirmed: acceptedCount,
      });

      this.logger.log(`User ${user.sub} left huddle ${dto.huddleId}`);
      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to leave huddle ${dto.huddleId} for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Start a huddle (creator only).
   */
  @SubscribeMessage('huddle.start')
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async handleStartHuddle(
    @MessageBody() dto: StartHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      await this.huddlesService.startHuddle(dto.huddleId, user.sub);

      // Notify all participants
      this.server.to(`huddle:${dto.huddleId}`).emit('huddle.started', {
        huddleId: dto.huddleId,
      });

      this.logger.log(`Huddle ${dto.huddleId} started by ${user.sub}`);
      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to start huddle ${dto.huddleId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Complete a huddle (creator only).
   */
  @SubscribeMessage('huddle.complete')
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async handleCompleteHuddle(
    @MessageBody() dto: CompleteHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      await this.huddlesService.completeHuddle(dto.huddleId, user.sub);

      // Notify all participants
      this.server.to(`huddle:${dto.huddleId}`).emit('huddle.completed', {
        huddleId: dto.huddleId,
      });

      this.logger.log(`Huddle ${dto.huddleId} completed by ${user.sub}`);
      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to complete huddle ${dto.huddleId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Cancel a huddle (creator only).
   */
  @SubscribeMessage('huddle.cancel')
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async handleCancelHuddle(
    @MessageBody() dto: CancelHuddleDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Get participant list BEFORE cancellation to ensure we notify everyone
      const huddle = await this.huddlesService.getHuddle(dto.huddleId);
      const participantUserIds = huddle.participants.map((p) => p.userId);

      await this.huddlesService.cancelHuddle(
        dto.huddleId,
        user.sub,
        dto.reason,
      );

      const sanitizedReason = dto.reason
        ? sanitizeForLog(dto.reason, 200)
        : 'Huddle was cancelled by the organizer';

      // Notify all participants in the huddle room
      this.server.to(`huddle:${dto.huddleId}`).emit('huddle.cancelled', {
        huddleId: dto.huddleId,
        reason: sanitizedReason,
      });

      // Also notify invited users who haven't joined the room yet
      for (const userId of participantUserIds) {
        this.server.to(`user:${userId}`).emit('huddle.cancelled', {
          huddleId: dto.huddleId,
          reason: sanitizedReason,
        });
      }

      this.logger.log(
        `Huddle ${dto.huddleId} cancelled by ${user.sub}. Reason: ${sanitizedReason}`,
      );
      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to cancel huddle ${dto.huddleId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get active huddles for an event.
   * Rate limited to prevent abuse.
   */
  @SubscribeMessage('huddle.list')
  @Throttle({ default: { limit: 30, ttl: 60000 } }) // 30 requests per minute
  async handleListHuddles(
    @MessageBody() dto: ListHuddlesDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify user is registered for the event
      await this.eventValidation.validateEventRegistration(user.sub, dto.eventId);

      const huddles = await this.huddlesService.getActiveHuddles(dto.eventId);

      return {
        success: true,
        huddles: huddles.map((h) => ({
          id: h.id,
          topic: h.topic,
          problemStatement: h.problemStatement,
          scheduledAt: h.scheduledAt,
          duration: h.duration,
          locationName: h.locationName,
          status: h.status,
          currentParticipants: h.participants.filter((p) => p.status === 'ACCEPTED').length,
          maxParticipants: h.maxParticipants,
        })),
      };
    } catch (error) {
      this.logger.error(
        `Failed to list huddles for event ${dto.eventId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get user's huddles (invitations and accepted).
   * Rate limited to prevent abuse.
   */
  @SubscribeMessage('huddle.my')
  @Throttle({ default: { limit: 30, ttl: 60000 } }) // 30 requests per minute
  async handleMyHuddles(
    @MessageBody() dto: MyHuddlesDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const userHuddles = await this.huddlesService.getUserHuddles(
        user.sub,
        dto.eventId,
      );

      return {
        success: true,
        huddles: userHuddles.map((hp) => ({
          id: hp.huddle.id,
          topic: hp.huddle.topic,
          problemStatement: hp.huddle.problemStatement,
          scheduledAt: hp.huddle.scheduledAt,
          duration: hp.huddle.duration,
          locationName: hp.huddle.locationName,
          status: hp.huddle.status,
          myStatus: hp.status,
          currentParticipants: hp.huddle.participants.length,
          maxParticipants: hp.huddle.maxParticipants,
          createdById: hp.huddle.createdById,
        })),
      };
    } catch (error) {
      this.logger.error(
        `Failed to get huddles for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
