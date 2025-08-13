import { Test, TestingModule } from '@nestjs/testing';
import { PublisherService } from './publisher.service';
import { REDIS_CLIENT } from '../redis.constants';

const mockRedis = { xadd: jest.fn() };

describe('PublisherService', () => {
  let service: PublisherService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PublisherService,
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    service = module.get<PublisherService>(PublisherService);
  });

  it('should call redis.xadd with a stringified payload', async () => {
    const stream = 'test-stream';
    const payload = { message: 'hello' };
    await service.publish(stream, payload);
    expect(mockRedis.xadd).toHaveBeenCalledWith(
      stream,
      '*',
      'data',
      JSON.stringify(payload),
    );
  });
});
