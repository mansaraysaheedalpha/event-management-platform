import { Test, TestingModule } from '@nestjs/testing';
import { SponsorsService } from './sponsors.service';
import { SponsorsGateway } from './sponsors.gateway';

const mockGateway = {
  broadcastNewLead: jest.fn(),
  broadcastLeadIntentUpdate: jest.fn(),
};

describe('SponsorsService', () => {
  let service: SponsorsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SponsorsService,
        { provide: SponsorsGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<SponsorsService>(SponsorsService);
    jest.clearAllMocks();
  });

  it('should route a LEAD_CAPTURED event to the correct gateway method', () => {
    const payload = {
      type: 'LEAD_CAPTURED' as const,
      sponsorId: 'sponsor-1',
      leadData: {
        user: { id: 'u1', name: 'Test' },
        action: 'DOWNLOAD',
        timestamp: '',
      },
    };
    service.handleMonetizationEvent(payload);
    expect(mockGateway.broadcastNewLead).toHaveBeenCalledWith(
      payload.sponsorId,
      payload.leadData,
    );
  });

  it('should route a LEAD_INTENT_UPDATE event to the correct gateway method', () => {
    const payload = {
      type: 'LEAD_INTENT_UPDATE' as const,
      sponsorId: 'sponsor-1',
      leadUserId: 'user-1',
      intentScore: 85,
      latestAction: 'PRICING_PAGE_VISIT',
    };
    service.handleMonetizationEvent(payload);
    expect(mockGateway.broadcastLeadIntentUpdate).toHaveBeenCalledWith(
      payload.sponsorId,
      expect.any(Object),
    );
  });
});
