import { Test, TestingModule } from '@nestjs/testing';
import { ProximityService } from './proximity.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';

const mockRedis = {
  geoadd: jest.fn(),
  georadiusbymember: jest.fn(),
};

describe('ProximityService', () => {
  let service: ProximityService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ProximityService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    service = module.get<ProximityService>(ProximityService);
    jest.clearAllMocks();
  });

  it('updateUserLocation should call redis.geoadd with correct parameters', async () => {
    const dto = { latitude: 40.7128, longitude: -74.006, idempotencyKey: 'k1' };
    await service.updateUserLocation('user-1', dto);
    // GEOADD expects longitude first, then latitude
    expect(mockRedis.geoadd).toHaveBeenCalledWith(
      'event:locations',
      dto.longitude,
      dto.latitude,
      'user-1',
    );
  });

  it('findNearbyUsers should filter out the user themselves from the results', async () => {
    const redisResponse = ['user-1', 'user-2', 'user-3']; // Redis includes the user
    mockRedis.georadiusbymember.mockResolvedValue(redisResponse);

    const result = await service.findNearbyUsers('user-1');

    expect(result).toEqual(['user-2', 'user-3']); // The service should remove user-1
  });
});
