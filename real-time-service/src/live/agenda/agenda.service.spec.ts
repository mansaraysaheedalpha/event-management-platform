import { Test, TestingModule } from '@nestjs/testing';
import {
  AgendaService,
  AgendaUpdatePayload,
  AgendaUpdateType,
} from './agenda.service';
import { AgendaGateway } from './agenda.gateway';

// Mocks
const mockAgendaGateway = {
  broadcastAgendaUpdate: jest.fn(),
};

describe('AgendaService', () => {
  let service: AgendaService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AgendaService,
        { provide: AgendaGateway, useValue: mockAgendaGateway },
      ],
    }).compile();
    service = module.get<AgendaService>(AgendaService);
    jest.clearAllMocks();
  });

  it('should call the gateway to broadcast the payload it receives', () => {
    const payload: AgendaUpdatePayload = {
      eventId: 'event-123',
      updateType: AgendaUpdateType.SESSION_ADDED,
      sessionData: { id: 'session-1', title: 'New Keynote' },
    };

    // Directly call the method that the @OnEvent decorator listens to
    service.handleAgendaUpdate(payload);

    expect(mockAgendaGateway.broadcastAgendaUpdate).toHaveBeenCalledWith(
      payload,
    );
  });
});
