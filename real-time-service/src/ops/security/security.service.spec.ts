import { Test, TestingModule } from '@nestjs/testing';
import { SecurityService } from './security.service';
import { SecurityGateway } from './security.gateway';

const mockGateway = {
  broadcastAccessControlUpdate: jest.fn(),
  broadcastSessionConflict: jest.fn(),
  broadcastSecurityAlert: jest.fn(),
};

describe('SecurityService', () => {
  let service: SecurityService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SecurityService,
        { provide: SecurityGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<SecurityService>(SecurityService);
    jest.clearAllMocks();
  });

  it('should route an ACCESS_CONTROL_UPDATE event correctly', () => {
    const payload = { type: 'ACCESS_CONTROL_UPDATE' } as any;
    service.handleSecurityEvent(payload);
    expect(mockGateway.broadcastAccessControlUpdate).toHaveBeenCalledWith(
      payload,
    );
  });

  it('should route a SESSION_CONFLICT_DETECTED event correctly', () => {
    const payload = { type: 'SESSION_CONFLICT_DETECTED' } as any;
    service.handleSecurityEvent(payload);
    expect(mockGateway.broadcastSessionConflict).toHaveBeenCalledWith(payload);
  });

  it('should route a generic alert correctly', () => {
    const payload = { type: 'UNUSUAL_LOGIN_ACTIVITY' } as any;
    service.handleSecurityEvent(payload);
    expect(mockGateway.broadcastSecurityAlert).toHaveBeenCalledWith(payload);
  });
});
