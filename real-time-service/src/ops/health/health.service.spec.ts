import { Test, TestingModule } from '@nestjs/testing';
import { HealthService } from './health.service';
import { HealthGateway } from './health.gateway';
import { HealthStatusDto } from './dto/health-status.dto';

const mockGateway = {
  broadcastHealthStatus: jest.fn(),
};

describe('HealthService', () => {
  let service: HealthService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        HealthService,
        { provide: HealthGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<HealthService>(HealthService);
    jest.clearAllMocks();
  });

  it('should call the gateway to broadcast the health status payload', () => {
    const payload = {
      service: 'API',
      status: 'OPERATIONAL',
      message: 'All systems normal.',
    } as HealthStatusDto;

    service.handleHealthEvent(payload);

    expect(mockGateway.broadcastHealthStatus).toHaveBeenCalledWith(payload);
  });
});
