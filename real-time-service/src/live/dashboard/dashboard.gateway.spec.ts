import { Test, TestingModule } from '@nestjs/testing';
import { DashboardGateway } from './dashboard.gateway';
import { DashboardService } from './dashboard.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

describe('DashboardGateway', () => {
  let gateway: DashboardGateway;
  let service: DashboardService;
  let server: any; // Use 'any' for easier mocking

  beforeAll(() => {
    jest.useFakeTimers();
    jest.spyOn(global, 'setTimeout');
    jest.spyOn(global, 'clearTimeout');
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        DashboardGateway,
        {
          provide: DashboardService,
          useValue: { getDashboardData: jest.fn() },
        },
      ],
    }).compile();
    gateway = module.get<DashboardGateway>(DashboardGateway);
    service = module.get<DashboardService>(DashboardService);

    // Create a fully mockable Server instance
    server = {
      to: jest.fn().mockReturnThis(),
      emit: jest.fn(),
      sockets: {
        adapter: {
          rooms: {
            get: jest.fn(), // We will mock this method's return value in each test
          },
        },
      },
    };
    (gateway as any).server = server;

    jest.clearAllMocks();
  });

  describe('handleJoinDashboard', () => {
    const mockHandshake = { query: { eventId: 'event-1' } } as any;
    const mockClient = { join: jest.fn(), handshake: mockHandshake } as any;

    it('should start the broadcast loop if it is the first admin to join', () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'admin-1',
        permissions: ['dashboard:read:live'],
      });
      gateway.handleJoinDashboard(mockClient);
      expect(mockClient.join).toHaveBeenCalledWith('dashboard:event-1');
      expect(setTimeout).toHaveBeenCalledTimes(1);
    });
  });

  describe('broadcast loop', () => {
    it('should fetch data and broadcast it after the interval', async () => {
      const dashboardData = { totalMessages: 100 };
      jest
        .spyOn(service, 'getDashboardData')
        .mockResolvedValue(dashboardData as any);

      // **FIX**: Mock `rooms.get` to return a Set with one client
      const mockRoom = new Set(['socket-1']);
      server.sockets.adapter.rooms.get.mockReturnValue(mockRoom);

      (gateway as any).scheduleNextBroadcast('event-1');
      await jest.advanceTimersByTimeAsync(5000);

      expect(service.getDashboardData).toHaveBeenCalledWith('event-1');
      expect(server.to).toHaveBeenCalledWith('dashboard:event-1');
      expect(server.emit).toHaveBeenCalledWith(
        'dashboard.update',
        dashboardData,
      );
      expect(setTimeout).toHaveBeenCalledTimes(2);
    });

    it('should stop the broadcast loop if no clients are listening', async () => {
      // **FIX**: Mock `rooms.get` to return an empty Set (or undefined)
      server.sockets.adapter.rooms.get.mockReturnValue(undefined);

      (gateway as any).scheduleNextBroadcast('event-1');
      await jest.advanceTimersByTimeAsync(5000);

      expect(service.getDashboardData).not.toHaveBeenCalled();
      expect(clearTimeout).toHaveBeenCalled();
    });
  });
});
