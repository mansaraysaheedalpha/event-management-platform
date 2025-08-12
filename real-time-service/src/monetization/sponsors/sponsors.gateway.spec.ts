import { Test, TestingModule } from '@nestjs/testing';
import { SponsorsGateway } from './sponsors.gateway';
import { SponsorsService } from './sponsors.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('SponsorsGateway', () => {
  let gateway: SponsorsGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [SponsorsGateway, { provide: SponsorsService, useValue: {} }],
    }).compile();
    gateway = module.get<SponsorsGateway>(SponsorsGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  describe('handleJoinLeadStream', () => {
    const mockClient = { join: jest.fn() } as any;

    it('should allow a sponsor with permission to join their room', () => {
      const mockSponsorUser = {
        sub: 'sponsor-user-1',
        permissions: ['sponsor:leads:read'],
        sponsorId: 'sponsor-abc',
      };
      mockGetAuthenticatedUser.mockReturnValue(mockSponsorUser);

      gateway.handleJoinLeadStream(mockClient);
      expect(mockClient.join).toHaveBeenCalledWith('sponsor:sponsor-abc');
    });

    it('should throw ForbiddenException if user lacks permission', () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: [],
      });
      expect(() => gateway.handleJoinLeadStream(mockClient)).toThrow(
        ForbiddenException,
      );
    });
  });

  describe('broadcastNewLead', () => {
    it('should broadcast a lead to the correct sponsor room', () => {
      const leadData = { user: { id: 'u1' } };
      gateway.broadcastNewLead('sponsor-xyz', leadData);
      expect(mockIoServer.to).toHaveBeenCalledWith('sponsor:sponsor-xyz');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'lead.captured.new',
        leadData,
      );
    });
  });
});
