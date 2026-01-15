//src/networking/analytics/analytics.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { NetworkingAnalyticsService } from './analytics.service';
import { PrismaService } from 'src/prisma.service';
import { ConnectionType, OutcomeType } from '@prisma/client';

const mockUser = (id: string, firstName: string, lastName: string) => ({
  id,
  firstName,
  lastName,
  email: `${firstName.toLowerCase()}@example.com`,
});

const createMockConnection = (
  id: string,
  userAId: string,
  userBId: string,
  eventId: string,
  overrides: Partial<{
    followUpSentAt: Date | null;
    followUpOpenedAt: Date | null;
    followUpRepliedAt: Date | null;
    meetingScheduled: boolean;
    outcomeType: OutcomeType | null;
    connectionType: ConnectionType;
    connectedAt: Date;
  }> = {},
) => ({
  id,
  userAId,
  userBId,
  eventId,
  connectionType: overrides.connectionType || ConnectionType.PROXIMITY_PING,
  connectedAt: overrides.connectedAt || new Date('2026-01-15T10:00:00Z'),
  initialMessage: null,
  followUpSentAt: overrides.followUpSentAt || null,
  followUpOpenedAt: overrides.followUpOpenedAt || null,
  followUpRepliedAt: overrides.followUpRepliedAt || null,
  meetingScheduled: overrides.meetingScheduled || false,
  meetingDate: null,
  outcomeType: overrides.outcomeType || null,
  outcomeNotes: null,
  outcomeReportedAt: null,
  userA: mockUser(userAId, 'User', userAId.slice(-1).toUpperCase()),
  userB: mockUser(userBId, 'User', userBId.slice(-1).toUpperCase()),
});

const mockPrisma = {
  connection: {
    findMany: jest.fn(),
  },
};

describe('NetworkingAnalyticsService', () => {
  let service: NetworkingAnalyticsService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        NetworkingAnalyticsService,
        { provide: PrismaService, useValue: mockPrisma },
      ],
    }).compile();
    service = module.get<NetworkingAnalyticsService>(NetworkingAnalyticsService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('getEventAnalytics', () => {
    it('should return comprehensive event analytics', async () => {
      const connections = [
        createMockConnection('conn-1', 'user-a', 'user-b', 'event-1', {
          followUpSentAt: new Date(),
          followUpOpenedAt: new Date(),
          outcomeType: OutcomeType.MEETING_HELD,
        }),
        createMockConnection('conn-2', 'user-a', 'user-c', 'event-1', {
          followUpSentAt: new Date(),
          connectionType: ConnectionType.DM_INITIATED,
        }),
        createMockConnection('conn-3', 'user-b', 'user-c', 'event-1'),
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const analytics = await service.getEventAnalytics('event-1');

      expect(analytics.totalConnections).toBe(3);
      expect(analytics.uniqueNetworkers).toBe(3);
      // attendeeCount is estimated as uniqueUsers * 2 = 6, so 3/6 = 0.5
      expect(analytics.averageConnectionsPerAttendee).toBe(0.5);
      expect(analytics.followUpsSent).toBe(2);
      expect(analytics.followUpsOpened).toBe(1);
      expect(analytics.reportedOutcomes).toBe(1);
      expect(analytics.meetingsScheduled).toBe(0);
      expect(analytics.followUpSentRate).toBeCloseTo(66.67, 1);
      expect(analytics.outcomeBreakdown).toHaveLength(1);
      expect(analytics.outcomeBreakdown[0].type).toBe('MEETING_HELD');
      expect(analytics.connectionsByType).toHaveLength(2);
      expect(analytics.topConnectors.length).toBeGreaterThan(0);
      expect(analytics.networkingScore).toBeGreaterThan(0);
    });

    it('should handle empty connections', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([]);

      const analytics = await service.getEventAnalytics('event-1');

      expect(analytics.totalConnections).toBe(0);
      expect(analytics.uniqueNetworkers).toBe(0);
      expect(analytics.followUpSentRate).toBe(0);
      expect(analytics.outcomeRate).toBe(0);
    });

    it('should calculate follow-up rates correctly', async () => {
      const connections = [
        createMockConnection('conn-1', 'user-a', 'user-b', 'event-1', {
          followUpSentAt: new Date(),
          followUpOpenedAt: new Date(),
          followUpRepliedAt: new Date(),
        }),
        createMockConnection('conn-2', 'user-a', 'user-c', 'event-1', {
          followUpSentAt: new Date(),
          followUpOpenedAt: new Date(),
        }),
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const analytics = await service.getEventAnalytics('event-1');

      expect(analytics.followUpSentRate).toBe(100);
      expect(analytics.followUpOpenRate).toBe(100);
      expect(analytics.followUpReplyRate).toBe(50);
    });
  });

  describe('getConnectionGraph', () => {
    it('should return nodes and edges for network visualization', async () => {
      const connections = [
        createMockConnection('conn-1', 'user-a', 'user-b', 'event-1', {
          outcomeType: OutcomeType.PARTNERSHIP,
        }),
        createMockConnection('conn-2', 'user-a', 'user-c', 'event-1'),
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const graph = await service.getConnectionGraph('event-1');

      expect(graph.nodes).toHaveLength(3);
      expect(graph.edges).toHaveLength(2);

      // user-a should have 2 connections
      const userANode = graph.nodes.find((n) => n.id === 'user-a');
      expect(userANode?.connectionCount).toBe(2);

      // Check edge with outcome
      const edgeWithOutcome = graph.edges.find((e) => e.connectionId === 'conn-1');
      expect(edgeWithOutcome?.hasOutcome).toBe(true);

      const edgeWithoutOutcome = graph.edges.find((e) => e.connectionId === 'conn-2');
      expect(edgeWithoutOutcome?.hasOutcome).toBe(false);
    });

    it('should handle empty connections', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([]);

      const graph = await service.getConnectionGraph('event-1');

      expect(graph.nodes).toHaveLength(0);
      expect(graph.edges).toHaveLength(0);
    });
  });

  describe('getUserAnalytics', () => {
    it('should return user networking analytics', async () => {
      const connections = [
        createMockConnection('conn-1', 'user-a', 'user-b', 'event-1', {
          followUpSentAt: new Date(),
          outcomeType: OutcomeType.JOB_REFERRAL,
        }),
        createMockConnection('conn-2', 'user-a', 'user-c', 'event-2'),
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const analytics = await service.getUserAnalytics('user-a');

      expect(analytics.totalConnections).toBe(2);
      expect(analytics.totalEvents).toBe(2);
      expect(analytics.followUpsSent).toBe(1);
      expect(analytics.followUpRate).toBe(50);
      expect(analytics.outcomesReported).toBe(1);
      expect(analytics.outcomeRate).toBe(50);
      expect(analytics.connectionsByEvent).toHaveLength(2);
      expect(analytics.recentConnections).toHaveLength(2);
    });

    it('should correctly identify other user in connections', async () => {
      const connections = [
        createMockConnection('conn-1', 'user-a', 'user-b', 'event-1'),
        createMockConnection('conn-2', 'user-c', 'user-a', 'event-1'), // user-a is userB here
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const analytics = await service.getUserAnalytics('user-a');

      expect(analytics.recentConnections[0].otherUserName).toBe('User B');
      expect(analytics.recentConnections[1].otherUserName).toBe('User C');
    });
  });

  describe('getOutcomeBreakdown', () => {
    it('should return breakdown of outcome types', async () => {
      const connections = [
        { outcomeType: OutcomeType.MEETING_HELD },
        { outcomeType: OutcomeType.MEETING_HELD },
        { outcomeType: OutcomeType.PARTNERSHIP },
        { outcomeType: OutcomeType.JOB_REFERRAL },
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const breakdown = await service.getOutcomeBreakdown('event-1');

      expect(breakdown).toHaveLength(3);
      expect(breakdown[0].type).toBe('MEETING_HELD');
      expect(breakdown[0].count).toBe(2);
      expect(breakdown[0].percentage).toBe(50);
    });

    it('should return empty array if no outcomes', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([]);

      const breakdown = await service.getOutcomeBreakdown('event-1');

      expect(breakdown).toHaveLength(0);
    });
  });

  describe('networking score calculation', () => {
    it('should calculate higher score for more engagement', async () => {
      // High engagement scenario
      const highEngagement = Array.from({ length: 50 }, (_, i) =>
        createMockConnection(`conn-${i}`, 'user-a', `user-${i}`, 'event-1', {
          followUpSentAt: new Date(),
          outcomeType: i < 10 ? OutcomeType.MEETING_HELD : null,
        }),
      );
      mockPrisma.connection.findMany.mockResolvedValue(highEngagement);

      const highScore = await service.getEventAnalytics('event-1');

      // Low engagement scenario
      const lowEngagement = [
        createMockConnection('conn-1', 'user-a', 'user-b', 'event-2'),
      ];
      mockPrisma.connection.findMany.mockResolvedValue(lowEngagement);

      const lowScore = await service.getEventAnalytics('event-2');

      expect(highScore.networkingScore).toBeGreaterThan(lowScore.networkingScore);
    });
  });
});
