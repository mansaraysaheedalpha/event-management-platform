import { Test, TestingModule } from '@nestjs/testing';
import { IncidentsGateway } from './incident.gateway';
import { IncidentsService } from './incidents.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockIncidentsService = {
  reportIncident: jest.fn(),
  updateIncidentStatus: jest.fn(),
};
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('IncidentsGateway', () => {
  let gateway: IncidentsGateway;

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
    join: jest.fn(), // Mock the join method
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        IncidentsGateway,
        { provide: IncidentsService, useValue: mockIncidentsService },
      ],
    }).compile();
    gateway = module.get<IncidentsGateway>(IncidentsGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  describe('handleJoinIncidentsStream', () => {
    it('should allow an admin with permission to join the incidents room', () => {
      const mockAdmin = {
        sub: 'admin-1',
        orgId: 'org-1',
        permissions: ['ops:incident:read'],
      };
      mockGetAuthenticatedUser.mockReturnValue(mockAdmin);

      gateway.handleJoinIncidentsStream(
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockClientSocket.join).toHaveBeenCalledWith('incidents:org-1');
    });

    it('should throw ForbiddenException if user lacks permission', () => {
      const mockUser = { sub: 'user-1', orgId: 'org-1', permissions: [] };
      mockGetAuthenticatedUser.mockReturnValue(mockUser);

      expect(() =>
        gateway.handleJoinIncidentsStream(
          mockClientSocket as AuthenticatedSocket,
        ),
      ).toThrow(ForbiddenException);
    });
  });

  describe('broadcastNewIncident', () => {
    it('should broadcast a new incident to the correct organization room', () => {
      const incident = { id: 'inc-1', organizationId: 'org-xyz' };
      gateway.broadcastNewIncident(incident as any); // Use 'as any' to simplify mock data

      expect(mockIoServer.to).toHaveBeenCalledWith('incidents:org-xyz');
      expect(mockIoServer.emit).toHaveBeenCalledWith('incident.new', incident);
    });
  });
});
