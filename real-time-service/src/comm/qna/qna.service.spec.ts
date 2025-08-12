import { Test, TestingModule } from '@nestjs/testing';
import { QnaService } from './qna.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { GamificationService } from 'src/gamification/gamification.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { HttpService } from '@nestjs/axios';
import { QnaGateway } from './qna.gateway';
import {
  ConflictException,
  ForbiddenException,
} from '@nestjs/common';
import { throwError } from 'rxjs';
import { AxiosError } from 'axios';

// **FIX**: More complete Redis mock
const mockRedisClient = {
  get: jest.fn(),
  set: jest.fn(),
  publish: jest.fn(),
  multi: jest.fn().mockReturnThis(),
  zadd: jest.fn().mockReturnThis(),
  zremrangebyscore: jest.fn().mockReturnThis(),
  zcard: jest.fn().mockReturnThis(),
  expire: jest.fn().mockReturnThis(),
  exec: jest.fn(),
};

const mockPrismaService = {
  question: { create: jest.fn(), findUnique: jest.fn(), update: jest.fn() },
  questionUpvote: { create: jest.fn() },
  userReference: { findUnique: jest.fn(), create: jest.fn() },
  answer: { create: jest.fn() },
  chatSession: { findUnique: jest.fn() },
  $transaction: jest.fn().mockImplementation((cb) => cb(mockPrismaService)),
};
const mockIdempotencyService = { checkAndSet: jest.fn() };
const mockPublisherService = { publish: jest.fn() };
const mockGamificationService = { awardPoints: jest.fn() };
const mockHttpService = { get: jest.fn() };
const mockQnaGateway = { broadcastModerationAlert: jest.fn() };

const mockUser = {
  id: 'user-1',
  email: 'test@test.com',
  firstName: 'Test',
  lastName: 'User',
};
const mockSessionId = 'session-1';
const mockQuestion = {
  id: 'q-1',
  text: 'A question?',
  authorId: mockUser.id,
  sessionId: mockSessionId,
  isAnswered: false,
};
const mockSession = {
  id: 'session-1',
  organizationId: 'org-1',
  eventId: 'event-1',
};

describe('QnaService', () => {
  let service: QnaService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        QnaService,
        { provide: PrismaService, useValue: mockPrismaService },
        { provide: IdempotencyService, useValue: mockIdempotencyService },
        { provide: PublisherService, useValue: mockPublisherService },
        { provide: GamificationService, useValue: mockGamificationService },
        { provide: HttpService, useValue: mockHttpService },
        { provide: QnaGateway, useValue: mockQnaGateway },
        { provide: REDIS_CLIENT, useValue: mockRedisClient },
      ],
    }).compile();
    service = module.get<QnaService>(QnaService);
    jest.clearAllMocks();
  });

  describe('askQuestion', () => {
    const askDto = { text: 'A question?', idempotencyKey: 'key-ask' };

    it('should create a question and use an existing user reference', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.userReference.findUnique.mockResolvedValue(mockUser);
      mockPrismaService.question.create.mockResolvedValue(mockQuestion);
      mockRedisClient.exec.mockResolvedValue([
        [null, 1],
        [null, 1],
        [null, 5],
        [null, 1],
      ]);
      mockRedisClient.get.mockResolvedValue(null); // **FIX**: Mock redis.get for analytics helper
      mockPrismaService.chatSession.findUnique.mockResolvedValue(mockSession); // **FIX**: Mock prisma session for analytics helper

      await service.askQuestion(
        mockUser.id,
        mockUser.email,
        mockSessionId,
        askDto,
      );
      expect(mockPrismaService.userReference.create).not.toHaveBeenCalled();
      expect(mockPrismaService.question.create).toHaveBeenCalled();
    });

    it('should create a user reference via HTTP fallback if not found locally', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.userReference.findUnique.mockResolvedValue(null);
      mockHttpService.get.mockReturnValueOnce(
        throwError(() => new AxiosError('Service Unavailable')),
      ); // Mock HTTP failure
      mockRedisClient.exec.mockResolvedValue([
        [null, 1],
        [null, 1],
        [null, 5],
        [null, 1],
      ]);
      mockRedisClient.get.mockResolvedValue(null);
      mockPrismaService.chatSession.findUnique.mockResolvedValue(mockSession);

      await service.askQuestion(
        mockUser.id,
        mockUser.email,
        mockSessionId,
        askDto,
      );
      expect(mockPrismaService.userReference.create).toHaveBeenCalledWith({
        data: {
          id: mockUser.id,
          email: mockUser.email,
          firstName: 'Guest',
          lastName: 'User',
        },
      });
    });

    it('should trigger a moderation alert if velocity threshold is exceeded', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.userReference.findUnique.mockResolvedValue(mockUser);
      mockPrismaService.question.create.mockResolvedValue(mockQuestion);
      // Mock Redis pipeline to return a high question count (e.g., 15)
      mockRedisClient.exec.mockResolvedValue([
        [null, 1],
        [null, 1],
        [null, 15],
        [null, 1],
      ]);

      await service.askQuestion(
        mockUser.id,
        mockUser.email,
        mockSessionId,
        askDto,
      );

      // We need to wait for the fire-and-forget promise to complete
      await new Promise(process.nextTick);

      expect(mockQnaGateway.broadcastModerationAlert).toHaveBeenCalled();
    });
  });

  describe('upvoteQuestion', () => {
    const upvoteDto = { questionId: 'q-1', idempotencyKey: 'key-upvote' };

    it('should successfully upvote a question', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.question.findUnique.mockResolvedValue(mockQuestion);
      mockPrismaService.questionUpvote.create.mockResolvedValue({});

      await service.upvoteQuestion('another-user-id', upvoteDto);

      expect(mockPrismaService.questionUpvote.create).toHaveBeenCalled();
    });

    it('should throw ForbiddenException when a user upvotes their own question', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.question.findUnique.mockResolvedValue(mockQuestion);

      await expect(
        service.upvoteQuestion(mockUser.id, upvoteDto),
      ).rejects.toThrow(ForbiddenException);
    });
  });

  describe('answerQuestion', () => {
    const answerDto = {
      questionId: 'q-1',
      answerText: 'This is the answer.',
      idempotencyKey: 'key-answer',
    };

    it('should answer a question and mark it as answered within a transaction', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.question.findUnique.mockResolvedValue(mockQuestion);

      await service.answerQuestion('admin-user', answerDto);

      expect(mockPrismaService.$transaction).toHaveBeenCalled();
      expect(mockPrismaService.answer.create).toHaveBeenCalled();
      expect(mockPrismaService.question.update).toHaveBeenCalledWith({
        where: { id: 'q-1' },
        data: { isAnswered: true },
      });
    });

    it('should throw ConflictException if the question is already answered', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.question.findUnique.mockResolvedValue({
        ...mockQuestion,
        isAnswered: true,
      });

      await expect(
        service.answerQuestion('admin-user', answerDto),
      ).rejects.toThrow(ConflictException);
    });
  });
});
