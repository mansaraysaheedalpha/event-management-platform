import { Test, TestingModule } from '@nestjs/testing';
import { AppGateway } from './app.gateway';
import { ConnectionService } from './system/connection/connection.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { extractTokenSafely } from './common/utils/auth.utils';

jest.mock('./common/utils/auth.utils');
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
});
