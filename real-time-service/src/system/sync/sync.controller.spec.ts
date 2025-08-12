import { Test, TestingModule } from '@nestjs/testing';
import { SyncController } from './sync.controller';
import { SyncService } from './sync.service';

const mockSyncService = { getChangesSince: jest.fn() };

describe('SyncController', () => {
  let controller: SyncController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [SyncController],
      providers: [{ provide: SyncService, useValue: mockSyncService }],
    }).compile();
    controller = module.get<SyncController>(SyncController);
  });

  it('should call the sync service with the correct user ID and timestamp', async () => {
    const mockReq = { user: { sub: 'user-123' } };
    const mockQuery = { since: new Date().toISOString() };
    mockSyncService.getChangesSince.mockResolvedValue([]);

    await controller.getChanges(mockReq, mockQuery);

    expect(mockSyncService.getChangesSince).toHaveBeenCalledWith(
      'user-123',
      mockQuery.since,
    );
  });
});
