import { Test, TestingModule } from '@nestjs/testing';
import { AgendaGateway } from './agenda.gateway';
import { AgendaUpdatePayload, AgendaUpdateType } from './agenda.service';

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('AgendaGateway', () => {
  let gateway: AgendaGateway;

  beforeEach(async () => {
    // This gateway has no dependencies, so the setup is simple
    const module: TestingModule = await Test.createTestingModule({
      providers: [AgendaGateway],
    }).compile();
    gateway = module.get<AgendaGateway>(AgendaGateway);
    (gateway as any).server = mockIoServer; // Manually attach the mock server
    jest.clearAllMocks();
  });

  it('should broadcast an agenda update to the correct event room', () => {
    const payload: AgendaUpdatePayload = {
      eventId: 'event-456',
      updateType: AgendaUpdateType.SESSION_CANCELED,
      sessionData: { id: 'session-2' },
    };

    gateway.broadcastAgendaUpdate(payload);

    expect(mockIoServer.to).toHaveBeenCalledWith('event:event-456');
    expect(mockIoServer.emit).toHaveBeenCalledWith('agenda.update', payload);
  });
});
