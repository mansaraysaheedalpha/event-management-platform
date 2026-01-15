import { Test, TestingModule } from '@nestjs/testing';
import { ProximityGateway } from './proximity.gateway';
import { ProximityService } from './proximity.service';
import { PrismaService } from 'src/prisma.service';
import { ConnectionsService } from '../connections/connections.service';
import { MatchingService } from '../matching/matching.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockEventId = 'event-123';

const mockProximityService = {
  updateUserLocation: jest.fn(),
  findNearbyUsers: jest.fn(),
};

const mockPrismaService = {
  userReference: { findUnique: jest.fn(), findMany: jest.fn() },
  connection: { findFirst: jest.fn() },
};

const mockConnectionsService = {
  createConnection: jest.fn(),
};

const mockMatchingService = {
  getEnhancedNearbyUsers: jest.fn(),
};

const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('ProximityGateway', () => {
  let gateway: ProximityGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ProximityGateway,
        { provide: ProximityService, useValue: mockProximityService },
        { provide: PrismaService, useValue: mockPrismaService },
        { provide: ConnectionsService, useValue: mockConnectionsService },
        { provide: MatchingService, useValue: mockMatchingService },
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
    mockPrismaService.connection.findFirst.mockResolvedValue(null);
    mockConnectionsService.createConnection.mockResolvedValue({});

    const dto = {
      targetUserId: 'user-2',
      eventId: mockEventId,
      message: 'Hi!',
      idempotencyKey: 'k1',
    };

    await gateway.handleProximityPing(dto, {} as any);

    expect(mockIoServer.to).toHaveBeenCalledWith('user:user-2');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'proximity.ping.received',
      expect.any(Object),
    );
    expect(mockConnectionsService.createConnection).toHaveBeenCalledWith(
      expect.objectContaining({
        userAId: 'user-1',
        userBId: 'user-2',
        eventId: mockEventId,
      }),
    );
  });

  it('handleProximityPing should skip duplicate connection if recent ping exists', async () => {
    mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
    mockPrismaService.userReference.findUnique.mockResolvedValue({
      firstName: 'Sender',
      lastName: 'User',
    });
    // Return an existing connection (simulating a recent ping)
    mockPrismaService.connection.findFirst.mockResolvedValue({
      id: 'existing-conn',
      userAId: 'user-1',
      userBId: 'user-2',
    });

    const dto = {
      targetUserId: 'user-2',
      eventId: mockEventId,
      message: 'Hi!',
      idempotencyKey: 'k1',
    };

    await gateway.handleProximityPing(dto, {} as any);

    expect(mockIoServer.to).toHaveBeenCalledWith('user:user-2');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'proximity.ping.received',
      expect.any(Object),
    );
    // Should NOT create a new connection since one already exists
    expect(mockConnectionsService.createConnection).not.toHaveBeenCalled();
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
