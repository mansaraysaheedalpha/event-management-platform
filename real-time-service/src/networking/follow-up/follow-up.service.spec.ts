//src/networking/follow-up/follow-up.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { FollowUpService, KAFKA_TOPICS } from './follow-up.service';
import { PrismaService } from 'src/prisma.service';
import { KafkaService } from 'src/shared/kafka/kafka.service';
import { ConnectionsService } from '../connections/connections.service';
import { NotFoundException } from '@nestjs/common';
import { ConnectionType } from '@prisma/client';

const mockConnectionWithContext = {
  id: 'conn-1',
  userAId: 'user-a',
  userBId: 'user-b',
  eventId: 'event-1',
  connectionType: ConnectionType.PROXIMITY_PING,
  connectedAt: new Date(),
  initialMessage: 'Nice to meet you!',
  followUpSentAt: null,
  followUpOpenedAt: null,
  followUpRepliedAt: null,
  meetingScheduled: false,
  meetingDate: null,
  outcomeType: null,
  outcomeNotes: null,
  outcomeReportedAt: null,
  userA: {
    id: 'user-a',
    firstName: 'John',
    lastName: 'Doe',
    email: 'john@example.com',
    avatarUrl: null,
  },
  userB: {
    id: 'user-b',
    firstName: 'Jane',
    lastName: 'Smith',
    email: 'jane@example.com',
    avatarUrl: null,
  },
  contexts: [
    { id: 'ctx-1', contextType: 'SHARED_SESSION', contextValue: 'AI Workshop' },
  ],
};

const mockPrisma = {
  connection: {
    findMany: jest.fn(),
  },
};

const mockKafkaService = {
  sendEvent: jest.fn(),
};

const mockConnectionsService = {
  getEventConnections: jest.fn(),
  getUserEventConnections: jest.fn(),
  getUserConnections: jest.fn(),
  getConnectionWithContext: jest.fn(),
  markFollowUpSent: jest.fn(),
  markFollowUpOpened: jest.fn(),
  markFollowUpReplied: jest.fn(),
};

describe('FollowUpService', () => {
  let service: FollowUpService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        FollowUpService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: KafkaService, useValue: mockKafkaService },
        { provide: ConnectionsService, useValue: mockConnectionsService },
      ],
    }).compile();
    service = module.get<FollowUpService>(FollowUpService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('scheduleEventFollowUps', () => {
    it('should return zero counts if no connections exist', async () => {
      mockConnectionsService.getEventConnections.mockResolvedValue([]);

      const result = await service.scheduleEventFollowUps('event-1');

      expect(result).toEqual({ scheduledCount: 0, userCount: 0 });
      expect(mockKafkaService.sendEvent).not.toHaveBeenCalled();
    });

    it('should schedule follow-ups for all users with connections', async () => {
      mockConnectionsService.getEventConnections.mockResolvedValue([
        mockConnectionWithContext,
      ]);

      const result = await service.scheduleEventFollowUps('event-1');

      // Each connection creates follow-ups for both users
      expect(result.scheduledCount).toBe(2); // 1 connection * 2 users
      expect(result.userCount).toBe(2);
      expect(mockKafkaService.sendEvent).toHaveBeenCalledTimes(2);
      expect(mockKafkaService.sendEvent).toHaveBeenCalledWith(
        KAFKA_TOPICS.FOLLOW_UP_EMAILS,
        expect.any(String),
        expect.objectContaining({
          type: 'CONNECTION_FOLLOW_UP',
          eventId: 'event-1',
        }),
      );
    });

    it('should use provided scheduledFor date', async () => {
      const scheduledFor = new Date('2026-02-01T10:00:00Z');
      mockConnectionsService.getEventConnections.mockResolvedValue([
        mockConnectionWithContext,
      ]);

      await service.scheduleEventFollowUps('event-1', scheduledFor);

      expect(mockKafkaService.sendEvent).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(String),
        expect.objectContaining({
          scheduledFor: scheduledFor.toISOString(),
        }),
      );
    });
  });

  describe('generateFollowUpEmail', () => {
    it('should generate email content with connections', async () => {
      mockConnectionsService.getUserEventConnections.mockResolvedValue([
        mockConnectionWithContext,
      ]);

      const result = await service.generateFollowUpEmail('user-a', 'event-1');

      expect(result.recipientEmail).toBe('john@example.com');
      expect(result.recipientName).toBe('John Doe');
      expect(result.connections).toHaveLength(1);
      expect(result.connections[0].name).toBe('Jane Smith');
      expect(result.oneClickActions.sendAllFollowUps).toBe(true);
    });

    it('should throw NotFoundException if no connections found', async () => {
      mockConnectionsService.getUserEventConnections.mockResolvedValue([]);

      await expect(
        service.generateFollowUpEmail('user-x', 'event-1'),
      ).rejects.toThrow(NotFoundException);
    });

    it('should generate suggested messages based on context', async () => {
      mockConnectionsService.getUserEventConnections.mockResolvedValue([
        mockConnectionWithContext,
      ]);

      const result = await service.generateFollowUpEmail('user-a', 'event-1');

      // Should use shared session context
      expect(result.connections[0].suggestedMessage).toContain('AI Workshop');
    });
  });

  describe('sendFollowUpMessage', () => {
    it('should send message via Kafka and mark follow-up sent', async () => {
      mockConnectionsService.getConnectionWithContext.mockResolvedValue(
        mockConnectionWithContext,
      );
      mockConnectionsService.markFollowUpSent.mockResolvedValue(undefined);

      const result = await service.sendFollowUpMessage(
        'conn-1',
        'Hello, great meeting you!',
        'user-a',
      );

      expect(result.success).toBe(true);
      expect(mockKafkaService.sendEvent).toHaveBeenCalledWith(
        KAFKA_TOPICS.FOLLOW_UP_EMAILS,
        'conn-1',
        expect.objectContaining({
          type: 'DIRECT_FOLLOW_UP',
          connectionId: 'conn-1',
          senderId: 'user-a',
          recipientId: 'user-b',
          recipientEmail: 'jane@example.com',
          message: 'Hello, great meeting you!',
        }),
      );
      expect(mockConnectionsService.markFollowUpSent).toHaveBeenCalledWith('conn-1');
    });
  });

  describe('trackOpen', () => {
    it('should mark follow-up as opened', async () => {
      mockConnectionsService.markFollowUpOpened.mockResolvedValue(undefined);

      await service.trackOpen('conn-1');

      expect(mockConnectionsService.markFollowUpOpened).toHaveBeenCalledWith('conn-1');
    });
  });

  describe('trackAction', () => {
    it('should mark follow-up as replied for reply actions', async () => {
      mockConnectionsService.markFollowUpReplied.mockResolvedValue(undefined);

      await service.trackAction('conn-1', 'reply');

      expect(mockConnectionsService.markFollowUpReplied).toHaveBeenCalledWith('conn-1');
    });

    it('should not mark as replied for non-reply actions', async () => {
      await service.trackAction('conn-1', 'view-profile');

      expect(mockConnectionsService.markFollowUpReplied).not.toHaveBeenCalled();
    });
  });

  describe('getEventFollowUpStats', () => {
    it('should calculate correct follow-up statistics', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([
        { followUpSentAt: new Date(), followUpOpenedAt: new Date(), followUpRepliedAt: new Date() },
        { followUpSentAt: new Date(), followUpOpenedAt: new Date(), followUpRepliedAt: null },
        { followUpSentAt: new Date(), followUpOpenedAt: null, followUpRepliedAt: null },
        { followUpSentAt: null, followUpOpenedAt: null, followUpRepliedAt: null },
      ]);

      const stats = await service.getEventFollowUpStats('event-1');

      expect(stats.totalScheduled).toBe(4);
      expect(stats.totalSent).toBe(3);
      expect(stats.totalOpened).toBe(2);
      expect(stats.totalReplied).toBe(1);
      expect(stats.openRate).toBeCloseTo(66.67, 1);
      expect(stats.replyRate).toBeCloseTo(33.33, 1);
    });

    it('should handle zero sent emails', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([
        { followUpSentAt: null, followUpOpenedAt: null, followUpRepliedAt: null },
      ]);

      const stats = await service.getEventFollowUpStats('event-1');

      expect(stats.openRate).toBe(0);
      expect(stats.replyRate).toBe(0);
    });
  });

  describe('getPendingFollowUps', () => {
    it('should return connections without follow-ups sent', async () => {
      const pendingConnection = { ...mockConnectionWithContext, followUpSentAt: null };
      const sentConnection = { ...mockConnectionWithContext, id: 'conn-2', followUpSentAt: new Date() };
      mockConnectionsService.getUserConnections.mockResolvedValue([
        pendingConnection,
        sentConnection,
      ]);

      const result = await service.getPendingFollowUps('user-a');

      expect(result).toHaveLength(1);
      expect(result[0].id).toBe('conn-1');
    });
  });
});
