import { Test, TestingModule } from '@nestjs/testing';
import { GamificationGateway } from './gamification.gateway';
import { GamificationService } from './gamification.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockGamificationService = {
  getLeaderboard: jest.fn(),
  getTeamLeaderboard: jest.fn(),
};
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('GamificationGateway', () => {
  let gateway: GamificationGateway;
  let module: TestingModule;

  const mockHandshake: Handshake = {
    headers: {},
    time: '',
    address: '',
    xdomain: false,
    secure: false,
    issued: 0,
    url: '',
    query: { sessionId: 'session-123' },
    auth: {},
  };
  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        GamificationGateway,
        { provide: GamificationService, useValue: mockGamificationService },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    gateway = module.get<GamificationGateway>(GamificationGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
  });

  // **Step 3: Add this block to gracefully close the module after all tests**
  afterAll(async () => {
    await module.close();
  });

  describe('handleRequestLeaderboard', () => {
    it('should call the service and return the data directly', async () => {
      const leaderboardData = { topEntries: [], currentUser: null };
      mockGamificationService.getLeaderboard.mockResolvedValue(leaderboardData);

      const result = await gateway.handleRequestLeaderboard(
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockGamificationService.getLeaderboard).toHaveBeenCalledWith(
        'session-123',
        'user-1',
      );
      expect(result.success).toBe(true);
      expect(result.data).toEqual(leaderboardData);
      expect(mockIoServer.emit).not.toHaveBeenCalled();
    });
  });

  describe('broadcastLeaderboardUpdate', () => {
    it('should fetch both leaderboards and broadcast them to the session room', async () => {
      mockGamificationService.getLeaderboard.mockResolvedValue({
        topEntries: [{ rank: 1 }],
      });
      mockGamificationService.getTeamLeaderboard.mockResolvedValue([
        { rank: 1 },
      ]);

      await gateway.broadcastLeaderboardUpdate('session-123');

      expect(mockGamificationService.getLeaderboard).toHaveBeenCalled();
      expect(mockGamificationService.getTeamLeaderboard).toHaveBeenCalled();
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'leaderboard.updated',
        expect.any(Object),
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'team.leaderboard.updated',
        expect.any(Object),
      );
    });
  });
});
