import { Test, TestingModule } from '@nestjs/testing';
import { HeatmapService } from './heatmap.service';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';

const mockRedis = {
  get: jest.fn(),
  set: jest.fn(),
  multi: jest.fn().mockReturnThis(),
  hincrby: jest.fn().mockReturnThis(),
  zadd: jest.fn().mockReturnThis(),
  expire: jest.fn().mockReturnThis(),
  exec: jest.fn(),
  hgetall: jest.fn(),
  zremrangebyscore: jest.fn().mockReturnThis(),
  zcard: jest.fn().mockReturnThis(),
};
const mockPrisma = {
  chatSession: { findUnique: jest.fn(), findMany: jest.fn() },
};

describe('HeatmapService', () => {
  let service: HeatmapService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        HeatmapService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    service = module.get<HeatmapService>(HeatmapService);
    jest.clearAllMocks();
  });

  it('should call redis multi pipeline with correct commands', async () => {
    // **FIX**: Add mocks to ensure _getSessionMetadata finds the session
    const mockSessionMeta = { eventId: 'event-1', organizationId: 'org-1' };
    mockRedis.get.mockResolvedValue(JSON.stringify(mockSessionMeta)); // Simulate cache hit

    const payload = { sessionId: 'session-1', type: 'MESSAGE_SENT' as const };

    await service.handleHeatmapEvent(payload);

    expect(mockRedis.multi).toHaveBeenCalled();
    expect(mockRedis.hincrby).toHaveBeenCalledWith(
      'heatmap:data:event-1',
      'session-1',
      1,
    );
    expect(mockRedis.zadd).toHaveBeenCalled();
    expect(mockRedis.exec).toHaveBeenCalled();
  });
});
