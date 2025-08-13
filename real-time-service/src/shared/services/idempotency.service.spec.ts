import { Test, TestingModule } from '@nestjs/testing';
import { IdempotencyService } from './idempotency.service';
import { REDIS_CLIENT } from '../redis.constants';

const mockRedis = { set: jest.fn() };

describe('IdempotencyService', () => {
  let service: IdempotencyService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        IdempotencyService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    service = module.get<IdempotencyService>(IdempotencyService);
  });

  it('should return true if the key is new and was set successfully', async () => {
    mockRedis.set.mockResolvedValue('OK');
    const result = await service.checkAndSet('new-key');
    expect(result).toBe(true);
    expect(mockRedis.set).toHaveBeenCalledWith(
      'idempotency:new-key',
      '1',
      'EX',
      60,
      'NX',
    );
  });

  it('should return false if the key already existed', async () => {
    mockRedis.set.mockResolvedValue(null); // Redis returns null if NX fails
    const result = await service.checkAndSet('existing-key');
    expect(result).toBe(false);
  });
});
