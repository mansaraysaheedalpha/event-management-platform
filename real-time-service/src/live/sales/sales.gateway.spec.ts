import { Test, TestingModule } from '@nestjs/testing';
import { SalesGateway } from './sales.gateway';
import { TicketAvailabilityDto } from './dto/ticket-availability.dto';

// Mock the Socket.IO server
const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('SalesGateway', () => {
  let gateway: SalesGateway;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [SalesGateway],
    }).compile();

    gateway = module.get<SalesGateway>(SalesGateway);
    (gateway as any).server = mockIoServer; // Manually attach the mock server
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  it('should broadcast a ticket availability update to the correct event room', () => {
    const payload: TicketAvailabilityDto = {
      eventId: 'event-123',
      ticketTypeId: 'ticket-abc',
      status: 'LOW_STOCK',
      ticketsRemaining: 10,
    };

    // Directly call the method that the @OnEvent decorator listens to
    gateway.handleTicketAvailabilityUpdate(payload);

    expect(mockIoServer.to).toHaveBeenCalledWith('event:event-123');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'ticket.availability.updated',
      payload,
    );
  });
});
