import { Test, TestingModule } from '@nestjs/testing';
import { PollsGateway } from './polls.gateway';
import { PollsService } from './polls.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockPollsService = {
  createPoll: jest.fn(),
  submitVote: jest.fn(),
  managePoll: jest.fn(),
  selectGiveawayWinner: jest.fn(),
};

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('PollsGateway', () => {
  let gateway: PollsGateway;

  const mockHandshake: Handshake = {
    headers: {},
    time: new Date().toUTCString(),
    address: '127.0.0.1',
    xdomain: false,
    secure: false,
    issued: Date.now(),
    url: '/socket.io/',
    query: { sessionId: 'session-123' },
    auth: {},
  };
  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PollsGateway,
        { provide: PollsService, useValue: mockPollsService },
      ],
    }).compile();

    gateway = module.get<PollsGateway>(PollsGateway);
    (gateway as any).server = mockIoServer;

    jest.clearAllMocks();
  });

  describe('handleCreatePoll', () => {
    const createPollDto = { question: 'Q', options: [], idempotencyKey: 'k1' };

    it('should create a poll and broadcast it if user has permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: ['poll:create'],
      });
      const newPoll = { id: 'poll-1' };
      mockPollsService.createPoll.mockResolvedValue(newPoll);

      const result = await gateway.handleCreatePoll(
        createPollDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockPollsService.createPoll).toHaveBeenCalled();
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith('poll.opened', newPoll);
      expect(result).toEqual({ success: true, pollId: 'poll-1' });
    });

    it('should throw ForbiddenException if user lacks permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: [],
      }); // No permission

      await expect(
        gateway.handleCreatePoll(
          createPollDto,
          mockClientSocket as AuthenticatedSocket,
        ),
      ).rejects.toThrow(ForbiddenException);
    });
  });

  describe('handleSubmitVote', () => {
    const submitVoteDto = {
      pollId: 'p1',
      optionId: 'o1',
      idempotencyKey: 'k2',
    };

    it('should submit a vote and broadcast updated results', async () => {
      mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
      const updatedPoll = { poll: { id: 'p1' } };
      mockPollsService.submitVote.mockResolvedValue(updatedPoll);

      await gateway.handleSubmitVote(
        submitVoteDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockPollsService.submitVote).toHaveBeenCalled();
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'poll.results.updated',
        updatedPoll,
      );
    });
  });

  describe('handleManagePoll', () => {
    const managePollDto = {
      pollId: 'p1',
      action: 'close' as const,
      idempotencyKey: 'k3',
    };

    it('should manage a poll if user has permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: ['poll:manage'],
      });
      const finalPoll = { poll: { id: 'p1', isActive: false } };
      mockPollsService.managePoll.mockResolvedValue(finalPoll);

      await gateway.handleManagePoll(
        managePollDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockPollsService.managePoll).toHaveBeenCalled();
      expect(mockIoServer.emit).toHaveBeenCalledWith('poll.closed', finalPoll);
    });
  });

  describe('handleStartGiveaway', () => {
    const startGiveawayDto = {
      pollId: 'p1',
      winningOptionId: 'o1',
      prize: 'T-Shirt',
      idempotencyKey: 'k4',
    };

    it('should start a giveaway and broadcast the winner if user has permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: ['poll:manage'],
      });
      const giveawayResult = { winner: { id: 'user-winner' } };
      mockPollsService.selectGiveawayWinner.mockResolvedValue(giveawayResult);

      await gateway.handleStartGiveaway(
        startGiveawayDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockPollsService.selectGiveawayWinner).toHaveBeenCalled();
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'poll.giveaway.winner',
        giveawayResult,
      );
    });
  });
});
