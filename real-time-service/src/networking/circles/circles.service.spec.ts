import { Test, TestingModule } from '@nestjs/testing';
import { CirclesService } from './circles.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { ConflictException, ForbiddenException } from '@nestjs/common';
import { Prisma } from '@prisma/client';

const mockPrisma = {
  $transaction: jest.fn().mockImplementation((cb) => cb(mockPrisma)),
  conversationCircle: {
    create: jest.fn(),
    findUnique: jest.fn(),
    update: jest.fn(),
  },
  conversationCircleParticipant: { create: jest.fn(), delete: jest.fn() },
};
const mockIdempotency = { checkAndSet: jest.fn() };

describe('CirclesService', () => {
  let service: CirclesService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        CirclesService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: IdempotencyService, useValue: mockIdempotency },
      ],
    }).compile();
    service = module.get<CirclesService>(CirclesService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('createCircle', () => {
    it('should create a circle and add the creator as a participant', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      const newCircle = { id: 'circle-1', topic: 'Test Topic' };
      mockPrisma.conversationCircle.create.mockResolvedValue(newCircle);
      mockPrisma.conversationCircle.findUnique.mockResolvedValue(newCircle);

      await service.createCircle('user-1', 'session-1', {
        topic: 'Test Topic',
        idempotencyKey: 'key-1',
      });

      expect(mockPrisma.$transaction).toHaveBeenCalled();
      expect(
        mockPrisma.conversationCircleParticipant.create,
      ).toHaveBeenCalledWith({
        data: { userId: 'user-1', circleId: 'circle-1' },
      });
    });
  });

  describe('joinCircle', () => {
    it('should throw ConflictException if user is already in the circle', async () => {
      const prismaError = new Prisma.PrismaClientKnownRequestError('', {
        code: 'P2002',
        clientVersion: '',
      });
      mockPrisma.conversationCircleParticipant.create.mockRejectedValue(
        prismaError,
      );

      await expect(service.joinCircle('user-1', 'circle-1')).rejects.toThrow(
        ConflictException,
      );
    });
  });

  describe('closeCircle', () => {
    const circle = { id: 'circle-1', creatorId: 'user-creator' };

    it('should allow the creator to close their own circle', async () => {
      mockPrisma.conversationCircle.findUnique.mockResolvedValue(circle);
      // **FIX**: Add the missing mock for the update operation
      mockPrisma.conversationCircle.update.mockResolvedValue(circle);

      await service.closeCircle('circle-1', 'user-creator', []);
      expect(mockPrisma.conversationCircle.update).toHaveBeenCalledWith({
        where: { id: 'circle-1' },
        data: { isActive: false },
      });
    });

    it('should allow a moderator to close any circle', async () => {
      mockPrisma.conversationCircle.findUnique.mockResolvedValue(circle);
      // **FIX**: Add the missing mock for the update operation
      mockPrisma.conversationCircle.update.mockResolvedValue(circle);

      await service.closeCircle('circle-1', 'admin-user', ['circles:manage']);
      expect(mockPrisma.conversationCircle.update).toHaveBeenCalled();
    });

    it('should throw ForbiddenException for an unauthorized user', async () => {
      mockPrisma.conversationCircle.findUnique.mockResolvedValue(circle);
      await expect(
        service.closeCircle('circle-1', 'random-user', []),
      ).rejects.toThrow(ForbiddenException);
    });
  });
});
