import { Test, TestingModule } from '@nestjs/testing';
import { MonetizationGateway } from './monetization.gateway';
import { MonetizationService } from './monetization.service';
import { WaitlistService } from '../waitlist/waitlist.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockWaitlistService = { addUserToWaitlist: jest.fn() };
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('MonetizationGateway', () => {
  let gateway: MonetizationGateway;
  let module: TestingModule;

  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: {
      headers: {},
      time: '',
      address: '',
      xdomain: false,
      secure: false,
      issued: 0,
      url: '',
      query: { sessionId: 'session-123' },
      auth: {},
    },
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        MonetizationGateway,
        { provide: MonetizationService, useValue: {} },
        { provide: WaitlistService, useValue: mockWaitlistService },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    gateway = module.get<MonetizationGateway>(MonetizationGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('handleJoinWaitlist', () => {
    it('should call the waitlist service with the correct user and session IDs', async () => {
      mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
      const dto = { idempotencyKey: 'key-1' };

      const result = await gateway.handleJoinWaitlist(
        dto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockWaitlistService.addUserToWaitlist).toHaveBeenCalledWith(
        'session-123',
        'user-1',
        'key-1',
      );
      expect(result.success).toBe(true);
    });
  });

  describe('broadcastAd', () => {
    it('should broadcast an ad to the correct event room', () => {
      const adContent = { id: 'ad-1', eventId: 'event-abc' };
      gateway.broadcastAd(adContent as any);
      expect(mockIoServer.to).toHaveBeenCalledWith('event:event-abc');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'monetization.ad.injected',
        adContent,
      );
    });
  });

  describe('sendUpsellToUser', () => {
    it('should send an upsell to the correct user room', () => {
      const offerContent = { id: 'offer-1' };
      gateway.sendUpsellToUser('user-xyz', offerContent as any);
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-xyz');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'monetization.upsell.new',
        offerContent,
      );
    });
  });
});
