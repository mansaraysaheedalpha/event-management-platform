import { Test, TestingModule } from '@nestjs/testing';
import { SubscriberService } from './subscriber.service';
import { REDIS_SUBSCRIBER_CLIENT } from '../redis.constants';
import { EventEmitter2 } from '@nestjs/event-emitter';

// Mock Redis subscriber client
const mockSubscriber = {
  on: jest.fn(),
  subscribe: jest.fn(),
};
const mockEventEmitter = { emit: jest.fn() };

describe('SubscriberService', () => {
  let service: SubscriberService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SubscriberService,
        { provide: REDIS_SUBSCRIBER_CLIENT, useValue: mockSubscriber },
        { provide: EventEmitter2, useValue: mockEventEmitter },
      ],
    }).compile();
    service = module.get<SubscriberService>(SubscriberService);
  });

  it('onModuleInit should subscribe to all Redis channels', async () => {
    await service.onModuleInit();
    expect(mockSubscriber.subscribe).toHaveBeenCalledWith(
      'agenda-updates',
      'audit-events',
      'security-events',
      'monetization-events',
      'system-health-events',
      'platform.analytics.check-in.v1',
      'sync-events',
      'ai-suggestions',
      'heatmap-events',
      'sales-events',
      'proximity-updates',
      'oracle.predictions.sentiment.v1',
      'capacity-events',
      'notification-events',
      'system-metrics-events',
    );
  });

  it('should handle an incoming message and emit it to the event bus', () => {
    const channel = 'test-channel';
    const message = { data: 'test-data' };
    const messageString = JSON.stringify(message);

    // Manually call the private method for testing purposes
    (service as any).handleIncomingMessage(channel, messageString);

    expect(mockEventEmitter.emit).toHaveBeenCalledWith(channel, message);
  });
});
