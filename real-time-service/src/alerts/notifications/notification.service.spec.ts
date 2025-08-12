import { Test, TestingModule } from '@nestjs/testing';
import { NotificationsService } from './notifications.service';
import { NotificationsGateway } from './notifications.gateway';
import { SessionReminderDto } from './dto/session-reminder.dto';

// Mocks
const mockGateway = {
  sendSessionReminder: jest.fn(),
  sendPersonalNotification: jest.fn(),
  broadcastEmergencyAlert: jest.fn(),
  broadcastScheduleChange: jest.fn(),
};

describe('NotificationsService', () => {
  let service: NotificationsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        NotificationsService,
        { provide: NotificationsGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<NotificationsService>(NotificationsService);
    jest.clearAllMocks();
  });

  it('should route a SESSION_REMINDER event to the correct gateway method', () => {
    const payload: SessionReminderDto = {
      type: 'SESSION_REMINDER',
      targetUserId: 'user-123',
      sessionData: { id: 's1', title: 'Keynote', startTime: '' },
      minutesUntilStart: 15,
    };

    service.handleNotificationEvent(payload);

    expect(mockGateway.sendSessionReminder).toHaveBeenCalledWith(
      payload.targetUserId,
      payload,
    );
    expect(mockGateway.broadcastEmergencyAlert).not.toHaveBeenCalled();
  });

  it('should route an EMERGENCY_ALERT event to the correct gateway method', () => {
    const payload = {
      type: 'EMERGENCY_ALERT' as const,
      eventId: 'event-1',
      alertType: 'FIRE' as const,
      message: 'Evacuate immediately.',
      severity: 'critical' as const,
    };

    service.handleNotificationEvent(payload);

    expect(mockGateway.broadcastEmergencyAlert).toHaveBeenCalledWith(
      payload.eventId,
      payload,
    );
    expect(mockGateway.sendSessionReminder).not.toHaveBeenCalled();
  });
});
