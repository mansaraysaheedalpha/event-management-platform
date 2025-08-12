import { Test, TestingModule } from '@nestjs/testing';
import { ContentService } from './content.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { BadRequestException } from '@nestjs/common';
import { PresentationState } from 'src/common/interfaces/presentation-state.interface';
import { ContentType, DropContentDto } from './dto/drop-content.dto'; // **FIX**: Import the ContentType enum

// Mocks
const mockPrisma = {
  presentation: { findUnique: jest.fn() },
  contentDropLog: { create: jest.fn() },
};
const mockIdempotency = { checkAndSet: jest.fn() };
const mockRedis = { get: jest.fn(), set: jest.fn() };

const sessionId = 'session-123';
const presentationData = { sessionId, slideUrls: ['url1', 'url2', 'url3'] };

describe('ContentService', () => {
  let service: ContentService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ContentService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: IdempotencyService, useValue: mockIdempotency },
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    service = module.get<ContentService>(ContentService);
    jest.clearAllMocks();
    mockIdempotency.checkAndSet.mockResolvedValue(true);
  });

  afterAll(async () => {
    await module.close();
  });

  describe('controlPresentation', () => {
    it('should START a presentation by fetching from Prisma and caching in Redis', async () => {
      mockRedis.get.mockResolvedValue(null);
      mockPrisma.presentation.findUnique.mockResolvedValue(presentationData);

      const newState = await service.controlPresentation(sessionId, {
        action: 'START',
        idempotencyKey: 'k1',
      });

      expect(mockPrisma.presentation.findUnique).toHaveBeenCalledWith({
        where: { sessionId },
      });
      expect(mockRedis.set).toHaveBeenCalledWith(
        `presentation:state:${sessionId}`,
        JSON.stringify({
          currentSlide: 0,
          totalSlides: 3,
          isActive: true,
          slideUrls: presentationData.slideUrls,
        }),
        'EX',
        expect.any(Number),
      );
      expect(newState.isActive).toBe(true);
      expect(newState.currentSlide).toBe(0);
    });

    it('should navigate to the NEXT_SLIDE for an active presentation', async () => {
      const activeState: PresentationState = {
        currentSlide: 0,
        totalSlides: 3,
        isActive: true,
        slideUrls: [],
      };
      mockRedis.get.mockResolvedValue(JSON.stringify(activeState));

      const newState = await service.controlPresentation(sessionId, {
        action: 'NEXT_SLIDE',
        idempotencyKey: 'k2',
      });

      expect(newState.currentSlide).toBe(1);
      expect(mockRedis.set).toHaveBeenCalled();
    });

    it('should not go past the last slide on NEXT_SLIDE', async () => {
      const activeState: PresentationState = {
        currentSlide: 2,
        totalSlides: 3,
        isActive: true,
        slideUrls: [],
      };
      mockRedis.get.mockResolvedValue(JSON.stringify(activeState));

      const newState = await service.controlPresentation(sessionId, {
        action: 'NEXT_SLIDE',
        idempotencyKey: 'k3',
      });

      expect(newState.currentSlide).toBe(2);
    });

    it('should throw BadRequestException if trying to navigate an inactive presentation', async () => {
      mockRedis.get.mockResolvedValue(null);

      await expect(
        service.controlPresentation(sessionId, {
          action: 'NEXT_SLIDE',
          idempotencyKey: 'k4',
        }),
      ).rejects.toThrow(BadRequestException);
    });

    it('should END a presentation', async () => {
      const activeState: PresentationState = {
        currentSlide: 1,
        totalSlides: 3,
        isActive: true,
        slideUrls: [],
      };
      mockRedis.get.mockResolvedValue(JSON.stringify(activeState));

      const newState = await service.controlPresentation(sessionId, {
        action: 'END',
        idempotencyKey: 'k5',
      });

      expect(newState.isActive).toBe(false);
      expect(mockRedis.set).toHaveBeenCalled();
    });
  });

  describe('handleContentDrop', () => {
    it('should log the content drop to the database', async () => {
      // **FIX**: Use the imported enum for the contentType
      const dropDto: DropContentDto = {
        contentType: ContentType.LINK,
        contentUrl: 'http://a.com',
        title: 'My Link',
        idempotencyKey: 'k6',
      };
      const dropper = { id: 'user-1', name: 'Presenter' };

      await service.handleContentDrop(dropDto, dropper, sessionId);

      expect(mockPrisma.contentDropLog.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          dropperId: dropper.id,
          sessionId,
          title: dropDto.title,
        }),
      });
    });
  });
});
