import { Test, TestingModule } from '@nestjs/testing';
import { PollsService } from './polls.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { GamificationService } from 'src/gamification/gamification.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { ConflictException, ForbiddenException } from '@nestjs/common';
import { Prisma } from '@prisma/client';

// Mock Data
const mockUser = { id: 'user-creator', firstName: 'Admin', lastName: 'User' };
const mockVoter = { id: 'user-voter-1' };
const mockSession = {
  id: 'session-1',
  organizationId: 'org-1',
  eventId: 'event-1',
};
const mockPoll = {
  id: 'poll-1',
  question: 'Favorite Color?',
  creatorId: mockUser.id,
  sessionId: mockSession.id,
  isActive: true,
  options: [
    { id: 'option-1', text: 'Red', pollId: 'poll-1', voteCount: 0 },
    { id: 'option-2', text: 'Blue', pollId: 'poll-1', voteCount: 0 },
  ],
};

// Mock Services
const mockPrismaService = {
  $transaction: jest.fn().mockImplementation((cb) => cb(mockPrismaService)),
  poll: {
    create: jest.fn(),
    findUnique: jest.fn(),
    update: jest.fn(),
  },
  pollOption: {
    createMany: jest.fn(),
  },
  pollVote: {
    create: jest.fn(),
    groupBy: jest.fn(),
    findUnique: jest.fn(),
    findMany: jest.fn(),
  },
  userReference: { findUnique: jest.fn() },
  chatSession: { findUnique: jest.fn() },
};
const mockIdempotencyService = { checkAndSet: jest.fn() };
const mockRedisClient = { publish: jest.fn(), get: jest.fn(), set: jest.fn() };
const mockPublisherService = { publish: jest.fn() };
const mockGamificationService = { awardPoints: jest.fn() };

describe('PollsService', () => {
  let service: PollsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PollsService,
        { provide: PrismaService, useValue: mockPrismaService },
        { provide: IdempotencyService, useValue: mockIdempotencyService },
        { provide: REDIS_CLIENT, useValue: mockRedisClient },
        { provide: PublisherService, useValue: mockPublisherService },
        { provide: GamificationService, useValue: mockGamificationService },
      ],
    }).compile();
    service = module.get<PollsService>(PollsService);
    jest.clearAllMocks();
  });

  describe('createPoll', () => {
    const createPollDto = {
      question: 'Favorite Color?',
      options: [{ text: 'Red' }, { text: 'Blue' }],
      idempotencyKey: 'key-create',
    };

    it('should create a poll and its options within a transaction', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.poll.create.mockResolvedValue({
        id: 'poll-1',
        ...createPollDto,
      });
      mockPrismaService.poll.findUnique.mockResolvedValue(mockPoll); // For the final return

      const result = await service.createPoll(
        mockUser.id,
        mockSession.id,
        createPollDto,
      );

      expect(mockPrismaService.$transaction).toHaveBeenCalled();
      expect(mockPrismaService.poll.create).toHaveBeenCalled();
      expect(mockPrismaService.pollOption.createMany).toHaveBeenCalled();
      expect(result).toEqual(mockPoll);
    });

    it('should throw ConflictException for a duplicate request', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(false);
      await expect(
        service.createPoll(mockUser.id, mockSession.id, createPollDto),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('submitVote', () => {
    const submitVoteDto = {
      pollId: 'poll-1',
      optionId: 'option-1',
      idempotencyKey: 'key-vote',
    };

    it('should submit a vote and return results successfully', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.poll.findUnique.mockResolvedValue(mockPoll); // Inside transaction
      mockPrismaService.pollVote.create.mockResolvedValue({}); // Vote created
      // Mock for getPollWithResults
      mockPrismaService.pollVote.groupBy.mockResolvedValue([
        { optionId: 'option-1', _count: { optionId: 1 } },
      ]);
      mockPrismaService.pollVote.findUnique.mockResolvedValue({
        optionId: 'option-1',
      });
      mockPrismaService.chatSession.findUnique.mockResolvedValue(mockSession);

      await service.submitVote(mockVoter.id, submitVoteDto);

      expect(mockPrismaService.pollVote.create).toHaveBeenCalled();
      expect(mockGamificationService.awardPoints).toHaveBeenCalled();
      expect(mockPublisherService.publish).toHaveBeenCalled(); // For analytics stream
    });

    it('should throw ForbiddenException when voting on an inactive poll', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.poll.findUnique.mockResolvedValue({
        ...mockPoll,
        isActive: false,
      });
      await expect(
        service.submitVote(mockVoter.id, submitVoteDto),
      ).rejects.toThrow(ForbiddenException);
    });

    it('should throw ConflictException if user has already voted', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.poll.findUnique.mockResolvedValue(mockPoll);
      const prismaError = new Prisma.PrismaClientKnownRequestError('', {
        code: 'P2002',
        clientVersion: '',
      });
      mockPrismaService.pollVote.create.mockRejectedValue(prismaError);

      await expect(
        service.submitVote(mockVoter.id, submitVoteDto),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('managePoll', () => {
    const managePollDto = {
      pollId: 'poll-1',
      action: 'close' as const,
      idempotencyKey: 'key-manage',
    };

    it('should close an active poll if requested by creator', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.poll.findUnique.mockResolvedValue(mockPoll);
      mockPrismaService.chatSession.findUnique.mockResolvedValue(mockSession); // For metadata helper
      mockPrismaService.poll.update.mockResolvedValue({
        ...mockPoll,
        isActive: false,
      });

      await service.managePoll(mockUser.id, managePollDto);

      expect(mockPrismaService.poll.update).toHaveBeenCalledWith({
        where: { id: 'poll-1' },
        data: { isActive: false },
      });
      expect(mockRedisClient.publish).toHaveBeenCalledWith(
        'audit-events',
        expect.any(String),
      );
      expect(mockPublisherService.publish).toHaveBeenCalled();
    });

    it('should throw ForbiddenException if user is not the poll creator', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.poll.findUnique.mockResolvedValue(mockPoll);

      await expect(
        service.managePoll('not-the-creator', managePollDto),
      ).rejects.toThrow(ForbiddenException);
    });
  });

  describe('selectGiveawayWinner', () => {
    const startGiveawayDto = {
      pollId: 'poll-1',
      winningOptionId: 'option-2',
      prize: 'A Free T-Shirt',
      idempotencyKey: 'key-giveaway',
    };
    const mockVoters = [
      { userId: 'voter-1' },
      { userId: 'voter-2' },
      { userId: 'voter-3' },
    ];
    const mockWinnerDetails = {
      id: 'voter-2',
      firstName: 'Winner',
      lastName: 'Person',
    };

    let randomSpy;

    beforeEach(() => {
      randomSpy = jest.spyOn(Math, 'random').mockReturnValue(0.5);
    });

    afterEach(() => {
      randomSpy.mockRestore();
    });

    it('should select a predictable winner and publish an audit event', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.pollVote.findMany.mockResolvedValue(mockVoters);
      mockPrismaService.userReference.findUnique.mockResolvedValue(
        mockWinnerDetails,
      );
      mockPrismaService.poll.findUnique.mockResolvedValue(mockPoll);
      mockRedisClient.get.mockResolvedValue(null);
      mockPrismaService.chatSession.findUnique.mockResolvedValue(mockSession);

      const result = await service.selectGiveawayWinner(
        startGiveawayDto,
        mockUser.id,
      );

      // **FIX**: First, assert the result is not null.
      expect(result).not.toBeNull();

      // Then, use a type guard (if statement) to safely access its properties.
      if (result) {
        expect(result.winner).toEqual(mockWinnerDetails);
      }

      expect(mockRedisClient.publish).toHaveBeenCalledWith(
        'audit-events',
        expect.any(String),
      );
    });

    it('should return null if there are no voters for the winning option', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.pollVote.findMany.mockResolvedValue([]);

      const result = await service.selectGiveawayWinner(
        startGiveawayDto,
        mockUser.id,
      );
      expect(result).toBeNull();
    });
  });
});
