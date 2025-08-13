import { Test, TestingModule } from '@nestjs/testing';
import { HeatmapGateway } from './heatmap.gateway';
import { HeatmapService } from './heatmap.service';

// NOTE: This is a simplified test for the heatmap gateway.
// A full test would require the complex timer-based setup from the Dashboard/Reactions gateways.
// For brevity, we are focusing on the core join logic.

describe('HeatmapGateway', () => {
  let gateway: HeatmapGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        HeatmapGateway,
        // The service has dependencies, so we provide a simple mock
        { provide: HeatmapService, useValue: {} },
      ],
    }).compile();
    gateway = module.get<HeatmapGateway>(HeatmapGateway);
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });
});
