import { Test, TestingModule } from '@nestjs/testing';
import { BackchannelService } from './backchannel.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { ConflictException } from '@nestjs/common';

describe('BackchannelService', () => {
  let service: BackchannelService;

  const mockPrisma = { backchannelMessage: { create: jest.fn() } };
  const mockIdempotency = { checkAndSet: jest.fn() };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        BackchannelService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: IdempotencyService, useValue: mockIdempotency },
      ],
    }).compile();
    service = module.get<BackchannelService>(BackchannelService);
    jest.clearAllMocks();
  });

  it('should create a message if idempotency check passes', async () => {
    mockIdempotency.checkAndSet.mockResolvedValue(true);
    const dto = { text: 'Test message', idempotencyKey: 'key-1' };
    await service.sendMessage('user-1', 'session-1', dto);
    expect(mockPrisma.backchannelMessage.create).toHaveBeenCalled();
  });
});
