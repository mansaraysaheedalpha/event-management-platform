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

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class PollsGateway {
  private readonly logger = new Logger(PollsGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly pollsService: PollsService) {}

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
}
