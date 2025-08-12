import { Test, TestingModule } from '@nestjs/testing';
import { SyncService } from './sync.service';
import { PrismaService } from 'src/prisma.service';
import { SyncGateway } from './sync.gateway';

const mockPrisma = {
  chatSession: { findUnique: jest.fn() },
  syncLog: { findMany: jest.fn() },
};
const mockGateway = { sendSyncUpdate: jest.fn() };

describe('SyncService', () => {
  let service: SyncService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SyncService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: SyncGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<SyncService>(SyncService);
    jest.clearAllMocks();
  });

  it('handleSyncEvent should send updates to all session participants', async () => {
    const mockSession = { participants: ['user-1', 'user-2'] };
    mockPrisma.chatSession.findUnique.mockResolvedValue(mockSession);
    const event = {
      resource: 'MESSAGE',
      action: 'CREATED',
      payload: { sessionId: 'session-1' },
    } as any;

    await service.handleSyncEvent(event);

    expect(mockGateway.sendSyncUpdate).toHaveBeenCalledTimes(2);
    expect(mockGateway.sendSyncUpdate).toHaveBeenCalledWith('user-1', event);
    expect(mockGateway.sendSyncUpdate).toHaveBeenCalledWith('user-2', event);
  });
});
