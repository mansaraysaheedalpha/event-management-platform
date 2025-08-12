// src/comm/chat/chat.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { ChatService } from './chat.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { GamificationService } from 'src/gamification/gamification.service';
import { ConfigService } from '@nestjs/config';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import {
  ConflictException,
  ForbiddenException,
  NotFoundException,
} from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { DeleteMessageDto } from './dto/delete-message.dto'; // Import the DTO

// Mock data
const mockUser = { id: 'user-1', firstName: 'John', lastName: 'Doe' };
const mockSession = {
  id: 'session-1',
  participants: ['user-1', 'user-2'],
  organizationId: 'org-1',
  eventId: 'event-1',
};
const mockMessage = {
  id: 'message-1',
  text: 'Hello World',
  authorId: mockUser.id,
  sessionId: mockSession.id,
  timestamp: new Date(),
  author: mockUser,
};

// Mocks for dependencies
const mockPrismaService = {
  chatSession: {
    findUnique: jest.fn(),
  },
  message: {
    findUnique: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  messageReaction: {
    findUnique: jest.fn(),
    create: jest.fn(),
    delete: jest.fn(),
  },
  $transaction: jest
    .fn()
    .mockImplementation((callback) => callback(mockPrismaService)),
};

const mockIdempotencyService = {
  checkAndSet: jest.fn(),
};

const mockRedisClient = {
  get: jest.fn(),
  set: jest.fn(),
  publish: jest.fn(),
};

const mockPublisherService = {
  publish: jest.fn(),
};

const mockGamificationService = {
  awardPoints: jest.fn(),
};

const mockConfigService = {
  get: jest.fn().mockReturnValue(300),
};

describe('ChatService', () => {
  let service: ChatService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ChatService,
        { provide: PrismaService, useValue: mockPrismaService },
        { provide: IdempotencyService, useValue: mockIdempotencyService },
        { provide: REDIS_CLIENT, useValue: mockRedisClient },
        { provide: PublisherService, useValue: mockPublisherService },
        { provide: GamificationService, useValue: mockGamificationService },
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();

    service = module.get<ChatService>(ChatService);
    jest.clearAllMocks();
  });

  describe('sendMessage', () => {
    const sendMessageDto = { text: 'Hello', idempotencyKey: 'idem-key-1' };

    it('should send a message and publish events successfully', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.chatSession.findUnique.mockResolvedValue(mockSession);
      mockPrismaService.message.create.mockResolvedValue(mockMessage);
      (mockPrismaService as any).syncLog = { createMany: jest.fn() };

      const sendMessageDto = { text: 'Hello', idempotencyKey: 'idem-key-1' };
      const result = await service.sendMessage(
        mockUser.id,
        mockSession.id,
        sendMessageDto,
      );

      // Give any fire-and-forget promises a chance to resolve
      await new Promise(process.nextTick);

      expect(result).toEqual(mockMessage);
      expect(mockPublisherService.publish).toHaveBeenCalledTimes(3); // heatmap, stream, sync
      expect(mockRedisClient.publish).toHaveBeenCalledWith(
        'analytics-events',
        expect.any(String),
      );
      expect(mockGamificationService.awardPoints).toHaveBeenCalledWith(
        mockUser.id,
        mockSession.id,
        'MESSAGE_SENT',
      );
    });

    it('should throw ConflictException on duplicate request', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(false);
      await expect(
        service.sendMessage(mockUser.id, mockSession.id, sendMessageDto),
      ).rejects.toThrow(ConflictException);
    });

    it('should throw NotFoundException if session does not exist', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.chatSession.findUnique.mockResolvedValue(null);
      await expect(
        service.sendMessage(mockUser.id, mockSession.id, sendMessageDto),
      ).rejects.toThrow(NotFoundException);
    });
  });

  describe('editMessage', () => {
    const editMessageDto = {
      messageId: 'message-1',
      newText: 'New text',
      idempotencyKey: 'idem-key-2',
    };

    it('should edit a message successfully', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.message.findUnique.mockResolvedValue(mockMessage);
      mockPrismaService.message.update.mockResolvedValue({
        ...mockMessage,
        text: editMessageDto.newText,
      });

      await service.editMessage(mockUser.id, editMessageDto);

      expect(mockPrismaService.message.findUnique).toHaveBeenCalledWith({
        where: { id: editMessageDto.messageId },
      });
      expect(mockPrismaService.message.update).toHaveBeenCalled();
      expect(mockPublisherService.publish).toHaveBeenCalledWith(
        'sync-events',
        expect.any(Object),
      );
    });

    it('should throw ForbiddenException if user is not the author', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.message.findUnique.mockResolvedValue({
        ...mockMessage,
        authorId: 'another-user',
      });
      await expect(
        service.editMessage(mockUser.id, editMessageDto),
      ).rejects.toThrow(ForbiddenException);
    });

    it('should throw ForbiddenException if edit window has passed', async () => {
      const oldTimestamp = new Date(Date.now() - 400 * 1000); // 400 seconds ago
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.message.findUnique.mockResolvedValue({
        ...mockMessage,
        timestamp: oldTimestamp,
      });

      await expect(
        service.editMessage(mockUser.id, editMessageDto),
      ).rejects.toThrow(ForbiddenException);
    });

    it('should throw NotFoundException if message does not exist', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.message.findUnique.mockResolvedValue(null);
      await expect(
        service.editMessage(mockUser.id, editMessageDto),
      ).rejects.toThrow(NotFoundException);
    });
  });

  describe('deleteMessage', () => {
    // Assuming DeleteMessageDto has an idempotencyKey
    const deleteDto: DeleteMessageDto = {
      messageId: mockMessage.id,
      idempotencyKey: 'idem-key-delete',
    };

    it('should allow author to delete their own message with correct permission', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true); // **ADDED**
      mockPrismaService.message.findUnique.mockResolvedValue(mockMessage);
      mockRedisClient.get.mockResolvedValue(JSON.stringify(mockSession));

      await service.deleteMessage(mockUser.id, deleteDto, ['chat:delete:own']);

      expect(mockPrismaService.message.delete).toHaveBeenCalledWith({
        where: { id: mockMessage.id },
      });
      expect(mockPublisherService.publish).toHaveBeenCalledWith(
        'sync-events',
        expect.any(Object),
      );
      expect(mockRedisClient.publish).toHaveBeenCalledWith(
        'audit-events',
        expect.any(String),
      );
    });

    it('should throw ConflictException on duplicate delete request', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(false);

      await expect(
        service.deleteMessage(mockUser.id, deleteDto, ['chat:delete:own']),
      ).rejects.toThrow(ConflictException);
      expect(mockPrismaService.message.findUnique).not.toHaveBeenCalled();
    });

    it('should allow moderator to delete any message', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.message.findUnique.mockResolvedValue({
        ...mockMessage,
        authorId: 'another-user',
      });
      mockRedisClient.get.mockResolvedValue(JSON.stringify(mockSession));

      await service.deleteMessage(mockUser.id, deleteDto, ['chat:delete:any']);

      expect(mockPrismaService.message.delete).toHaveBeenCalledWith({
        where: { id: mockMessage.id },
      });
    });

    it('should throw ForbiddenException if user lacks permission', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.message.findUnique.mockResolvedValue({
        ...mockMessage,
        authorId: 'another-user',
      });

      await expect(
        service.deleteMessage(mockUser.id, deleteDto, ['chat:delete:own']),
      ).rejects.toThrow(ForbiddenException);
    });
  });

  describe('reactToMessage', () => {
    const reactDto = {
      messageId: mockMessage.id,
      emoji: '👍',
      idempotencyKey: 'idem-key-react',
    };

    it('should throw ConflictException on duplicate react request', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(false);
      await expect(
        service.reactToMessage(mockUser.id, reactDto),
      ).rejects.toThrow(ConflictException);
      expect(
        mockPrismaService.messageReaction.findUnique,
      ).not.toHaveBeenCalled();
    });

    it('should add a reaction if one does not exist', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.messageReaction.findUnique.mockResolvedValue(null);
      mockPrismaService.messageReaction.create.mockResolvedValue({});
      mockPrismaService.message.findUnique.mockResolvedValue({
        ...mockMessage,
        reactions: [{ userId: mockUser.id, emoji: '👍' }],
      });

      const result = await service.reactToMessage(mockUser.id, reactDto);

      expect(mockPrismaService.messageReaction.create).toHaveBeenCalled();

      // **FIXED**: Add a check to ensure the result is not null before testing its properties.
      expect(result).not.toBeNull();
      if (result) {
        expect(result.reactionsSummary['👍']).toBe(1);
      }
    });

    it('should remove a reaction if it already exists', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.messageReaction.findUnique.mockResolvedValue({
        id: 'reaction-1',
        ...reactDto,
        userId: mockUser.id,
      });
      mockPrismaService.messageReaction.delete.mockResolvedValue({});
      mockPrismaService.message.findUnique.mockResolvedValue({
        ...mockMessage,
        reactions: [],
      });

      const result = await service.reactToMessage(mockUser.id, reactDto);

      expect(mockPrismaService.messageReaction.delete).toHaveBeenCalled();

      // **FIXED**: Add a check to ensure the result is not null before testing its properties.
      expect(result).not.toBeNull();
      if (result) {
        expect(result.reactionsSummary).toEqual({});
      }
    });

    it('should throw NotFoundException when reacting to a non-existent message', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.messageReaction.findUnique.mockResolvedValue(null);
      const prismaError = new Prisma.PrismaClientKnownRequestError(
        'Foreign key constraint failed',
        {
          code: 'P2003',
          clientVersion: 'x.x.x',
        },
      );
      mockPrismaService.messageReaction.create.mockRejectedValue(prismaError);

      await expect(
        service.reactToMessage(mockUser.id, reactDto),
      ).rejects.toThrow(NotFoundException);
    });
  });
});
