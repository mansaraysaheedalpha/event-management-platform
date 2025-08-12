//src/comm/polls/polls.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Logger, NotFoundException } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { CreatePollDto } from './dto/create-poll.dto';
import { PollsService } from './polls.service';
import { ManagePollDto } from './dto/manage-polls.dto';
import { SubmitVoteDto } from './dto/submit-vote.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { StartGiveawayDto } from './dto/start-giveaway.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class PollsGateway {
  private readonly logger = new Logger(PollsGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly pollsService: PollsService) {}

  /**
   * Handles incoming request to create a new poll.
   * Checks user permissions, calls service to create poll,
   * and broadcasts the new poll to the session room.
   * @param dto - Data required to create the poll.
   * @param client - The connected authenticated socket client.
   * @returns success status and new poll ID or error info.
   */
  @SubscribeMessage('poll.create')
  async handleCreatePoll(
    @MessageBody() dto: CreatePollDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:create';
    // We now safely check the permissions array.
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to create a poll.',
      );
    }

    try {
      // We must `await` the promise from the service.
      const newPoll = await this.pollsService.createPoll(
        user.sub,
        sessionId,
        dto,
      );

      // We must check for null before using the result.
      if (!newPoll) {
        throw new Error('Poll creation returned an unexpected null result.');
      }

      const publicRoom = `session:${sessionId}`;
      const eventName = 'poll.opened';

      this.server.to(publicRoom).emit(eventName, newPoll);
      this.logger.log(
        `New poll ${newPoll.id} broadcasted to room ${publicRoom}`,
      );

      return { success: true, pollId: newPoll.id };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to create poll for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Handles incoming vote submission for a poll.
   * Submits the vote via service, then broadcasts updated poll results.
   * @param dto - Vote submission details.
   * @param client - The connected authenticated socket client.
   * @returns success status and poll ID or error info.
   */
  @SubscribeMessage('poll.vote.submit')
  async handleSubmitVote(
    @MessageBody() dto: SubmitVoteDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedPollWithResults = await this.pollsService.submitVote(
        user.sub,
        dto,
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'poll.results.updated';

      this.server.to(publicRoom).emit(eventName, updatedPollWithResults);
      this.logger.log(
        `Updated poll results for ${dto.pollId} broadcasted to room ${publicRoom}`,
      );

      return { success: true, pollId: dto.pollId };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to submit vote for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Handles requests to manage a poll (e.g., closing a poll).
   * Checks user permissions, performs management action via service,
   * then broadcasts final poll results to the session room.
   * @param dto - Poll management instructions.
   * @param client - The connected authenticated socket client.
   * @returns success status, poll ID, and final status or error info.
   */
  @SubscribeMessage('poll.manage')
  async handleManagePoll(
    @MessageBody() dto: ManagePollDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:manage';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to manage polls.',
      );
    }

    try {
      const finalPollResults = await this.pollsService.managePoll(
        user.sub,
        dto,
      );

      if (!finalPollResults) {
        throw new NotFoundException(
          'Poll to manage was not found or already in the desired state.',
        );
      }

      const publicRoom = `session:${sessionId}`;
      const eventName = 'poll.closed';

      this.server.to(publicRoom).emit(eventName, finalPollResults);
      this.logger.log(
        `Final poll results for ${dto.pollId} broadcasted to room ${publicRoom}`,
      );

      return { success: true, pollId: dto.pollId, finalStatus: 'closed' };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to manage poll for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Handles an admin starting a giveaway for a poll.
   */
  @SubscribeMessage('poll.giveaway.start')
  async handleStartGiveaway(
    @MessageBody() dto: StartGiveawayDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:manage'; // Same permission as closing a poll
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to manage giveaways.',
      );
    }

    try {
      const giveawayResult = await this.pollsService.selectGiveawayWinner(
        dto,
        user.sub,
      );

      if (giveawayResult) {
        const publicRoom = `session:${sessionId}`;
        const eventName = 'poll.giveaway.winner';
        this.server.to(publicRoom).emit(eventName, giveawayResult);
        this.logger.log(
          `Broadcasted giveaway winner for poll ${dto.pollId} to room ${publicRoom}`,
        );
      }

      return { success: true, winner: giveawayResult?.winner };
    } catch (error) {
      this.logger.error(
        `Failed to start giveaway for admin ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
