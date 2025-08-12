import { Test, TestingModule } from '@nestjs/testing';
import { ProximityGateway } from './proximity.gateway';
import { ProximityService } from './proximity.service';
import { PrismaService } from 'src/prisma.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockProximityService = {
  updateUserLocation: jest.fn(),
  findNearbyUsers: jest.fn(),
};
const mockPrismaService = { userReference: { findUnique: jest.fn() } };
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('ProximityGateway', () => {
  let gateway: ProximityGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ProximityGateway,
        { provide: ProximityService, useValue: mockProximityService },
        { provide: PrismaService, useValue: mockPrismaService },
      ],
    }).compile();
    gateway = module.get<ProximityGateway>(ProximityGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  it('handleProximityPing should emit a ping to the target user', async () => {
    mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
    mockPrismaService.userReference.findUnique.mockResolvedValue({
      firstName: 'Sender',
      lastName: 'User',
    });
    const dto = {
      targetUserId: 'user-2',
      message: 'Hi!',
      idempotencyKey: 'k1',
    };

    await gateway.handleProximityPing(dto, {} as any);

    expect(mockIoServer.to).toHaveBeenCalledWith('user:user-2');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'proximity.ping.received',
      expect.any(Object),
    );
  });

  it('handleProximityUpdate should emit a roster update to the target user', () => {
    const payload = { userId: 'user-1', nearbyUsers: [] };
    gateway.handleProximityUpdate(payload);
    expect(mockIoServer.to).toHaveBeenCalledWith('user:user-1');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'proximity.roster.updated',
      payload,
    );
  });
});
