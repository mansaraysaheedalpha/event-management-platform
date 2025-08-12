import { Test, TestingModule } from '@nestjs/testing';
import { DmService } from './dm.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { ConfigService } from '@nestjs/config';
import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  NotFoundException,
} from '@nestjs/common';

const mockPrismaService = {
  directMessage: {
    create: jest.fn(),
    updateMany: jest.fn(),
    findUnique: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  conversation: {
    findFirst: jest.fn(),
    create: jest.fn(),
  },
  $transaction: jest.fn().mockImplementation((cb) => cb(mockPrismaService)),
};

const mockIdempotencyService = { checkAndSet: jest.fn() };
const mockPublisherService = { publish: jest.fn() };
const mockConfigService = { get: jest.fn().mockReturnValue(300) };

describe('DmService', () => {
  let service: DmService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        DmService,
        { provide: PrismaService, useValue: mockPrismaService },
        { provide: IdempotencyService, useValue: mockIdempotencyService },
        { provide: PublisherService, useValue: mockPublisherService },
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();

    service = module.get<DmService>(DmService);
    jest.clearAllMocks();
  });

  describe('sendMessage', () => {
    const senderId = 'user-1';
    const sendDmDto = {
      recipientId: 'user-2',
      text: 'Hello!',
      idempotencyKey: 'key-1',
    };
    const mockConversation = { id: 'convo-1' };
    const mockMessage = { id: 'dm-1', ...sendDmDto, senderId };

    it('should send a message successfully by creating a new conversation', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.conversation.findFirst.mockResolvedValue(null);
      mockPrismaService.conversation.create.mockResolvedValue(mockConversation);
      mockPrismaService.directMessage.create.mockResolvedValue(mockMessage);

      const result = await service.sendMessage(senderId, sendDmDto);

      expect(mockPrismaService.conversation.findFirst).toHaveBeenCalled();
      expect(mockPrismaService.conversation.create).toHaveBeenCalled();
      expect(mockPrismaService.directMessage.create).toHaveBeenCalledWith(
        expect.objectContaining({
          data: {
            text: sendDmDto.text,
            senderId,
            conversationId: mockConversation.id,
          },
        }),
      );
      expect(result).toEqual(mockMessage);
    });

    it('should throw BadRequestException when sending a message to oneself', async () => {
      await expect(
        service.sendMessage(senderId, { ...sendDmDto, recipientId: senderId }),
      ).rejects.toThrow(BadRequestException);
    });

    it('should throw ConflictException on duplicate request', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(false);
      await expect(service.sendMessage(senderId, sendDmDto)).rejects.toThrow(
        ConflictException,
      );
    });
  });

  describe('markAsDelivered', () => {
    const recipientId = 'user-2';
    const deliveryDto = { messageId: 'dm-1', idempotencyKey: 'key-2' };

    it('should mark a message as delivered and return the updated message', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.directMessage.updateMany.mockResolvedValue({
        count: 1,
      });
      mockPrismaService.directMessage.findUnique.mockResolvedValue({
        id: 'dm-1',
        isDelivered: true,
      });

      const result = await service.markAsDelivered(recipientId, deliveryDto);

      expect(mockPrismaService.directMessage.updateMany).toHaveBeenCalled();
      expect(mockPublisherService.publish).toHaveBeenCalled();
      expect(result).not.toBeNull();
    });

    it('should return null if no message was updated', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.directMessage.updateMany.mockResolvedValue({
        count: 0,
      });

      const result = await service.markAsDelivered(recipientId, deliveryDto);
      expect(result).toBeNull();
      expect(mockPublisherService.publish).not.toHaveBeenCalled();
    });
  });

  describe('editMessage', () => {
    const userId = 'user-1';
    const editDto = {
      messageId: 'dm-1',
      newText: 'Hi there',
      idempotencyKey: 'key-edit',
    };
    const mockMessage = {
      id: 'dm-1',
      senderId: userId,
      timestamp: new Date(),
      conversation: { participants: [{ id: 'user-1' }, { id: 'user-2' }] },
    };

    it('should edit a message successfully', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.directMessage.findUnique.mockResolvedValue(mockMessage);
      mockPrismaService.directMessage.update.mockResolvedValue({
        ...mockMessage,
        text: 'Hi there',
      });

      const result = await service.editMessage(userId, editDto);

      expect(mockPrismaService.directMessage.update).toHaveBeenCalled();
      expect(result.participantIds).toEqual(['user-1', 'user-2']);
      expect(result.updatedMessage.text).toBe('Hi there');
    });

    it('should throw ForbiddenException if user is not the sender', async () => {
      mockIdempotencyService.checkAndSet.mockResolvedValue(true);
      mockPrismaService.directMessage.findUnique.mockResolvedValue({
        ...mockMessage,
        senderId: 'another-user',
      });

      await expect(service.editMessage(userId, editDto)).rejects.toThrow(
        ForbiddenException,
      );
    });
  });
});
