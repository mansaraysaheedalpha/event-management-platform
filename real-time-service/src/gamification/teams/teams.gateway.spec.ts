import { Test, TestingModule } from '@nestjs/testing';
import { TeamsGateway } from './teams.gateway';
import { TeamsService } from './teams.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockTeamsService = {
  createTeam: jest.fn(),
  joinTeam: jest.fn(),
  leaveTeam: jest.fn(),
};
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('TeamsGateway', () => {
  let gateway: TeamsGateway;
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
  const mockUser = { sub: 'user-1' };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        TeamsGateway,
        { provide: TeamsService, useValue: mockTeamsService },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    gateway = module.get<TeamsGateway>(TeamsGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue(mockUser);
  });

  afterAll(async () => {
    await module.close();
  });

  describe('handleCreateTeam', () => {
    it('should call the service and broadcast the new team', async () => {
      const createDto = { name: 'New Team', idempotencyKey: 'k1' };
      const newTeam = { id: 'team-1', name: 'New Team' };
      mockTeamsService.createTeam.mockResolvedValue(newTeam);

      await gateway.handleCreateTeam(
        createDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockTeamsService.createTeam).toHaveBeenCalledWith(
        mockUser.sub,
        'session-123',
        createDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith('team.created', newTeam);
    });
  });

  describe('handleJoinTeam', () => {
    it('should call the service and broadcast a roster update', async () => {
      const joinDto = { teamId: 'team-1', idempotencyKey: 'k2' };
      const updatedTeam = { id: 'team-1', members: [] };
      mockTeamsService.joinTeam.mockResolvedValue(updatedTeam);

      await gateway.handleJoinTeam(
        joinDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockTeamsService.joinTeam).toHaveBeenCalledWith(
        mockUser.sub,
        joinDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'team.roster.updated',
        updatedTeam,
      );
    });
  });
});
