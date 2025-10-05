import { Test, TestingModule } from '@nestjs/testing';
import { AppGateway } from './app.gateway';
import { ConnectionService } from './system/connection/connection.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import {
  extractTokenSafely,
  getAuthenticatedUser,
} from './common/utils/auth.utils';
import { DashboardService } from './live/dashboard/dashboard.service';
import { ForbiddenException } from '@nestjs/common';

jest.mock('./common/utils/auth.utils', () => ({
  extractTokenSafely: jest.fn(),
  getAuthenticatedUser: jest.fn((client) => client.data.user),
}));

const mockExtractTokenSafely = extractTokenSafely as jest.Mock;

describe('AppGateway', () => {
  let gateway: AppGateway;
  let connectionService: ConnectionService;
  let jwtService: JwtService;

  const mockClient = {
    id: 'socket-123',
    data: {},
    join: jest.fn(),
    emit: jest.fn(),
    disconnect: jest.fn(),
  } as any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AppGateway,
        {
          provide: ConnectionService,
          useValue: { startHeartbeat: jest.fn(), stopHeartbeat: jest.fn() },
        },
        { provide: JwtService, useValue: { verify: jest.fn() } },
        {
          provide: ConfigService,
          useValue: { getOrThrow: jest.fn().mockReturnValue('secret') },
        },
        {
          provide: DashboardService,
          useValue: {
            getDashboardData: jest.fn(),
            getActiveEventIdsForOrg: jest.fn(),
          },
        },
      ],
    }).compile();
    gateway = module.get<AppGateway>(AppGateway);
    connectionService = module.get<ConnectionService>(ConnectionService);
    jwtService = module.get<JwtService>(JwtService);
    jest.clearAllMocks();
  });

  describe('handleConnection', () => {
    it('should authenticate a client with a valid token and start heartbeat', async () => {
      const mockPayload = { sub: 'user-1', email: 'test@test.com' };
      mockExtractTokenSafely.mockReturnValue('valid-token');
      jest.spyOn(jwtService, 'verify').mockReturnValue(mockPayload);

      await gateway.handleConnection(mockClient);

      expect(mockClient.data.user).toEqual(mockPayload);
      expect(mockClient.join).toHaveBeenCalledWith('user:user-1');
      expect(connectionService.startHeartbeat).toHaveBeenCalledWith(mockClient);
      expect(mockClient.emit).toHaveBeenCalledWith('connectionAcknowledged', {
        userId: 'user-1',
      });
    });

    it('should disconnect a client with an invalid token', async () => {
      mockExtractTokenSafely.mockReturnValue('invalid-token');
      jest.spyOn(jwtService, 'verify').mockImplementation(() => {
        throw new Error('Invalid token');
      });

      await gateway.handleConnection(mockClient);

      expect(mockClient.disconnect).toHaveBeenCalledWith(true);
      expect(connectionService.startHeartbeat).not.toHaveBeenCalled();
    });

    it('should disconnect a client with no token', async () => {
      mockExtractTokenSafely.mockReturnValue(null); // No token found

      await gateway.handleConnection(mockClient);

      expect(mockClient.disconnect).toHaveBeenCalledWith(true);
      expect(jest.spyOn(jwtService, 'verify')).not.toHaveBeenCalled();
    });
  });

  describe('handleDisconnect', () => {
    it('should stop the heartbeat for the disconnected client', () => {
      gateway.handleDisconnect(mockClient);
      expect(connectionService.stopHeartbeat).toHaveBeenCalledWith(
        mockClient.id,
      );
    });
  });

  describe('handleJoinDashboard', () => {
    const mockDashboardClient = {
      id: 'socket-456',
      data: {
        user: {
          sub: 'admin-user',
          email: 'admin@test.com',
          permissions: ['dashboard:read:live'],
        },
      },
      handshake: {
        query: { eventId: 'event-1' },
      },
      join: jest.fn(),
    } as any;

    it('should allow a user with permissions to join a dashboard room', () => {
      const response = gateway.handleJoinDashboard(mockDashboardClient);
      expect(response.success).toBe(true);
      expect(mockDashboardClient.join).toHaveBeenCalledWith(
        'dashboard:event-1',
      );
    });

    it('should deny a user without permissions', () => {
      const clientWithoutPerms = {
        ...mockDashboardClient,
        data: { user: { ...mockDashboardClient.data.user, permissions: [] } },
      };
      expect(() => gateway.handleJoinDashboard(clientWithoutPerms)).toThrow(
        ForbiddenException,
      );
    });

    it('should return an error if eventId is missing', () => {
      const clientWithoutEventId = {
        ...mockDashboardClient,
        handshake: { query: {} },
      };
      const response = gateway.handleJoinDashboard(clientWithoutEventId as any);
      expect(response.success).toBe(false);
      expect(response.error).toBe('Event ID is required to join a dashboard.');
    });
  });
});
