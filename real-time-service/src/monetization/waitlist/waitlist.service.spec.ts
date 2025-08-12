import { Test, TestingModule } from '@nestjs/testing';
import { WaitlistService } from './waitlist.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { ConflictException } from '@nestjs/common';

// Mocks
const mockRedis = {
  rpush: jest.fn(),
  lpop: jest.fn(),
  llen: jest.fn(),
  del: jest.fn(),
  expire: jest.fn(),
};
const mockIdempotency = { checkAndSet: jest.fn() };

describe('WaitlistService', () => {
  let service: WaitlistService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        WaitlistService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
        { provide: IdempotencyService, useValue: mockIdempotency },
      ],
    }).compile();
    service = module.get<WaitlistService>(WaitlistService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('addUserToWaitlist', () => {
    it('should add a user to the Redis list', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      await service.addUserToWaitlist('session-1', 'user-1', 'key-1');
      expect(mockRedis.rpush).toHaveBeenCalledWith(
        'waitlist:session-1',
        'user-1',
      );
    });

    it('should throw ConflictException on duplicate request', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(false);
      await expect(
        service.addUserToWaitlist('session-1', 'user-1', 'key-1'),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('getNextUserFromWaitlist', () => {
    it('should retrieve a user and clean up the list if it becomes empty', async () => {
      mockRedis.lpop.mockResolvedValue('user-1');
      mockRedis.llen.mockResolvedValue(0); // List is now empty

      const userId = await service.getNextUserFromWaitlist('session-1');

      expect(userId).toBe('user-1');
      expect(mockRedis.del).toHaveBeenCalledWith('waitlist:session-1');
      expect(mockRedis.expire).not.toHaveBeenCalled();
    });

    it('should return null if the waitlist is empty', async () => {
      mockRedis.lpop.mockResolvedValue(null);
      const userId = await service.getNextUserFromWaitlist('session-1');
      expect(userId).toBeNull();
    });
  });
});
