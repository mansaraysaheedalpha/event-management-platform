import { Test, TestingModule } from '@nestjs/testing';
import { NotificationsGateway } from './notifications.gateway';
import { NotificationsService } from './notifications.service';

// Mock Socket.IO server
const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('NotificationsGateway', () => {
  let gateway: NotificationsGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        NotificationsGateway,
        // The gateway depends on the service, so we provide a mock.
        { provide: NotificationsService, useValue: {} },
      ],
    }).compile();
    gateway = module.get<NotificationsGateway>(NotificationsGateway);
    (gateway as any).server = mockIoServer; // Manually attach the mock server
    jest.clearAllMocks();
  });

  it('sendSessionReminder should emit to the correct user room', () => {
    const userId = 'user-abc';
    const payload = { type: 'SESSION_REMINDER' } as any;

    gateway.sendSessionReminder(userId, payload);

    expect(mockIoServer.to).toHaveBeenCalledWith(`user:${userId}`);
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'notification.session_reminder',
      payload,
    );
  });

  it('broadcastEmergencyAlert should emit to the correct event room', () => {
    const eventId = 'event-123';
    const payload = { type: 'EMERGENCY_ALERT' } as any;

    gateway.broadcastEmergencyAlert(eventId, payload);

    expect(mockIoServer.to).toHaveBeenCalledWith(`event:${eventId}`);
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'notification.emergency',
      payload,
    );
  });
});
