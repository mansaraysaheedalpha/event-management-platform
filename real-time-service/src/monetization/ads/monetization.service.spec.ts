import { Test, TestingModule } from '@nestjs/testing';
import { MonetizationService } from './monetization.service';
import { HttpService } from '@nestjs/axios';
import { MonetizationGateway } from './monetization.gateway';
import { WaitlistService } from '../waitlist/waitlist.service';
import { of } from 'rxjs';

const mockHttp = { get: jest.fn() };
const mockGateway = {
  broadcastAd: jest.fn(),
  sendUpsellToUser: jest.fn(),
  sendWaitlistNotification: jest.fn(),
};
const mockWaitlist = { getNextUserFromWaitlist: jest.fn() };

describe('MonetizationService', () => {
  let service: MonetizationService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        MonetizationService,
        { provide: HttpService, useValue: mockHttp },
        { provide: MonetizationGateway, useValue: mockGateway },
        { provide: WaitlistService, useValue: mockWaitlist },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    service = module.get<MonetizationService>(MonetizationService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  it('should fetch ad content and broadcast it for an AD_INJECTION event', async () => {
    const adContent = { id: 'ad-1', eventId: 'event-1' };
    mockHttp.get.mockReturnValue(of({ data: adContent, status: 200 } as any));

    await service.handleMonetizationEvent({
      type: 'AD_INJECTION',
      eventId: 'event-1',
      adId: 'ad-1',
    });

    expect(mockHttp.get).toHaveBeenCalled();
    expect(mockGateway.broadcastAd).toHaveBeenCalledWith(adContent);
  });

  it('should get the next user from the waitlist and send a notification for SPOT_AVAILABLE', async () => {
    const nextUserId = 'user-next';
    const waitlistOffer = {
      title: 'Spot Available!',
      message: 'Join now',
      join_token: 'xyz',
      expires_at: '',
    };
    mockWaitlist.getNextUserFromWaitlist.mockResolvedValue(nextUserId);
    mockHttp.get.mockReturnValue(
      of({ data: waitlistOffer, status: 200 } as any),
    );

    await service.handleMonetizationEvent({
      type: 'SPOT_AVAILABLE',
      sessionId: 'session-1',
    });

    expect(mockWaitlist.getNextUserFromWaitlist).toHaveBeenCalledWith(
      'session-1',
    );
    expect(mockHttp.get).toHaveBeenCalled();
    expect(mockGateway.sendWaitlistNotification).toHaveBeenCalledWith(
      nextUserId,
      expect.any(Object),
    );
  });

  it('should do nothing if no user is on the waitlist for SPOT_AVAILABLE', async () => {
    mockWaitlist.getNextUserFromWaitlist.mockResolvedValue(null);
    await service.handleMonetizationEvent({
      type: 'SPOT_AVAILABLE',
      sessionId: 'session-1',
    });
    expect(mockHttp.get).not.toHaveBeenCalled();
    expect(mockGateway.sendWaitlistNotification).not.toHaveBeenCalled();
  });
});
