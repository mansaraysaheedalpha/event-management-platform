import { Test, TestingModule } from '@nestjs/testing';
import { DashboardService } from './dashboard.service';
import { DashboardGateway } from './dashboard.gateway';
import { REDIS_CLIENT } from 'src/shared/redis.constants';

// Mocks
const mockRedis = {
  hincrby: jest.fn(),
  lpush: jest.fn(),
  ltrim: jest.fn(),
  multi: jest.fn().mockReturnThis(),
  hgetall: jest.fn().mockReturnThis(),
  lrange: jest.fn().mockReturnThis(),
  exec: jest.fn(),
  smembers: jest.fn(),
};
const mockDashboardGateway = {
  broadcastCapacityUpdate: jest.fn(),
  broadcastSystemMetrics: jest.fn(),
};

describe('DashboardService', () => {
  let service: DashboardService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        DashboardService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
        { provide: DashboardGateway, useValue: mockDashboardGateway },
      ],
    }).compile();
    service = module.get<DashboardService>(DashboardService);
    jest.clearAllMocks();
  });

  describe('handleAnalyticsEvent', () => {
    it('should increment the correct Redis hash field for a MESSAGE_SENT event', async () => {
      const payload = { type: 'MESSAGE_SENT', eventId: 'event-1' };
      await service.handleAnalyticsEvent(payload);
      expect(mockRedis.hincrby).toHaveBeenCalledWith(
        'dashboard:analytics:event-1',
        'totalMessages',
        1,
      );
    });

    it('should update the check-in feed for a CHECK_IN_PROCESSED event', async () => {
      const checkInData = { id: 'user-1', name: 'Test User' };
      const payload = {
        type: 'CHECK_IN_PROCESSED',
        eventId: 'event-1',
        checkInData,
      };

      await service.handleAnalyticsEvent(payload);

      expect(mockRedis.lpush).toHaveBeenCalledWith(
        'dashboard:feed:check-in:event-1',
        JSON.stringify(checkInData),
      );
      expect(mockRedis.ltrim).toHaveBeenCalledWith(
        'dashboard:feed:check-in:event-1',
        0,
        9,
      );
    });

    it('should ignore a malformed payload', async () => {
      const payload = { eventId: 'event-1' }; // Missing 'type'
      await service.handleAnalyticsEvent(payload);
      expect(mockRedis.hincrby).not.toHaveBeenCalled();
    });
  });

  describe('getDashboardData', () => {
    it('should fetch and parse data correctly from a Redis pipeline', async () => {
      const mockAnalytics = { totalMessages: '10', totalVotes: '5' };
      const mockFeed = [JSON.stringify({ id: 'user-1', name: 'Test User' })];
      // Mock the tuple response from multi().exec()
      mockRedis.exec.mockResolvedValue([
        [null, mockAnalytics],
        [null, mockFeed],
      ]);

      const data = await service.getDashboardData('event-1');

      expect(data.totalMessages).toBe(10);
      expect(data.totalVotes).toBe(5);
      expect(data.totalQuestions).toBe(0); // Ensure defaults work
      expect(data.liveCheckInFeed.length).toBe(1);
      expect(data.liveCheckInFeed[0].name).toBe('Test User');
    });
  });
});
