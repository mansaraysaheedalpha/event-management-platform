import { Test, TestingModule } from '@nestjs/testing';
import { ReactionsService } from './reactions.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { PublisherService } from 'src/shared/services/publisher.service';
import { ReactionsGateway } from './reactions.gateway';

const mockRedis = { hincrby: jest.fn(), expire: jest.fn() };
const mockPublisher = { publish: jest.fn() };
const mockGateway = { broadcastMoodAnalytics: jest.fn() };

describe('ReactionsService', () => {
  let service: ReactionsService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ReactionsService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
        { provide: PublisherService, useValue: mockPublisher },
        { provide: ReactionsGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<ReactionsService>(ReactionsService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    // <-- Add this
    await module.close();
  });

  describe('addReaction', () => {
    it('should increment the emoji count, set expiration, and publish events', async () => {
      const sessionId = 'session-1';
      const userId = 'user-1';
      const emoji = '🔥';

      await service.addReaction(sessionId, userId, emoji);

      expect(mockRedis.hincrby).toHaveBeenCalledWith(
        `reactions:${sessionId}`,
        emoji,
        1,
      );
      expect(mockRedis.expire).toHaveBeenCalledWith(
        `reactions:${sessionId}`,
        300,
        'NX',
      );
      expect(mockPublisher.publish).toHaveBeenCalledWith('heatmap-events', {
        sessionId,
      });
      expect(mockPublisher.publish).toHaveBeenCalledWith(
        'platform.events.live.reaction.v1',
        expect.any(Object),
      );
    });
  });

  describe('handleMoodAnalytics', () => {
    it('should call the gateway to broadcast the analytics payload', () => {
      const payload = {
        sessionId: 'session-1',
        analytics: { mood: 'positive' },
      };
      service.handleMoodAnalytics(payload);
      expect(mockGateway.broadcastMoodAnalytics).toHaveBeenCalledWith(
        payload.sessionId,
        payload.analytics,
      );
    });
  });
});
