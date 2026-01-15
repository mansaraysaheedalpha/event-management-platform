//src/networking/connections/connections.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { ConnectionsService } from './connections.service';
import { PrismaService } from 'src/prisma.service';
import { NotFoundException } from '@nestjs/common';
import { ConnectionType, OutcomeType } from '@prisma/client';

const mockConnection = {
  id: 'conn-1',
  userAId: 'user-a',
  userBId: 'user-b',
  eventId: 'event-1',
  connectionType: ConnectionType.PROXIMITY_PING,
  connectedAt: new Date(),
  initialMessage: null,
  followUpSentAt: null,
  followUpOpenedAt: null,
  followUpRepliedAt: null,
  meetingScheduled: false,
  meetingDate: null,
  outcomeType: null,
  outcomeNotes: null,
  outcomeReportedAt: null,
};

const mockConnectionWithContext = {
  ...mockConnection,
  userA: { id: 'user-a', firstName: 'John', lastName: 'Doe', email: 'john@example.com', avatarUrl: null },
  userB: { id: 'user-b', firstName: 'Jane', lastName: 'Smith', email: 'jane@example.com', avatarUrl: null },
  contexts: [{ id: 'ctx-1', contextType: 'SHARED_SESSION', contextValue: 'session-1' }],
};

const mockPrisma = {
  connection: {
    upsert: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
    update: jest.fn(),
  },
};

describe('ConnectionsService', () => {
  let service: ConnectionsService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ConnectionsService,
        { provide: PrismaService, useValue: mockPrisma },
      ],
    }).compile();
    service = module.get<ConnectionsService>(ConnectionsService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('createConnection', () => {
    it('should create a new connection with normalized user order', async () => {
      mockPrisma.connection.upsert.mockResolvedValue(mockConnection);

      const result = await service.createConnection({
        userAId: 'user-b', // Intentionally reversed to test sorting
        userBId: 'user-a',
        eventId: 'event-1',
        connectionType: ConnectionType.PROXIMITY_PING,
      });

      expect(mockPrisma.connection.upsert).toHaveBeenCalledWith({
        where: {
          userAId_userBId_eventId: {
            userAId: 'user-a', // Should be sorted
            userBId: 'user-b',
            eventId: 'event-1',
          },
        },
        update: {},
        create: {
          userAId: 'user-a',
          userBId: 'user-b',
          eventId: 'event-1',
          connectionType: ConnectionType.PROXIMITY_PING,
          initialMessage: undefined,
        },
      });
      expect(result).toEqual(mockConnection);
    });

    it('should update initialMessage if connection exists', async () => {
      mockPrisma.connection.upsert.mockResolvedValue({
        ...mockConnection,
        initialMessage: 'Hello!',
      });

      await service.createConnection({
        userAId: 'user-a',
        userBId: 'user-b',
        eventId: 'event-1',
        initialMessage: 'Hello!',
      });

      expect(mockPrisma.connection.upsert).toHaveBeenCalledWith(
        expect.objectContaining({
          update: { initialMessage: 'Hello!' },
        }),
      );
    });
  });

  describe('getUserEventConnections', () => {
    it('should return connections for a user at an event', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([mockConnectionWithContext]);

      const result = await service.getUserEventConnections('user-a', 'event-1');

      expect(mockPrisma.connection.findMany).toHaveBeenCalledWith({
        where: {
          eventId: 'event-1',
          OR: [{ userAId: 'user-a' }, { userBId: 'user-a' }],
        },
        include: expect.any(Object),
        orderBy: { connectedAt: 'desc' },
      });
      expect(result).toEqual([mockConnectionWithContext]);
    });
  });

  describe('getConnectionWithContext', () => {
    it('should return a connection with full context', async () => {
      mockPrisma.connection.findUnique.mockResolvedValue(mockConnectionWithContext);

      const result = await service.getConnectionWithContext('conn-1');

      expect(result).toEqual(mockConnectionWithContext);
    });

    it('should throw NotFoundException if connection not found', async () => {
      mockPrisma.connection.findUnique.mockResolvedValue(null);

      await expect(service.getConnectionWithContext('non-existent')).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('markFollowUpSent', () => {
    it('should update followUpSentAt timestamp', async () => {
      mockPrisma.connection.update.mockResolvedValue(mockConnection);

      await service.markFollowUpSent('conn-1');

      expect(mockPrisma.connection.update).toHaveBeenCalledWith({
        where: { id: 'conn-1' },
        data: { followUpSentAt: expect.any(Date) },
      });
    });
  });

  describe('reportOutcome', () => {
    it('should update connection with outcome data', async () => {
      const outcomeData = {
        outcomeType: OutcomeType.MEETING_HELD,
        outcomeNotes: 'Great meeting!',
        meetingScheduled: true,
        meetingDate: '2026-02-01T10:00:00Z',
      };
      mockPrisma.connection.update.mockResolvedValue({
        ...mockConnection,
        ...outcomeData,
      });

      const result = await service.reportOutcome('conn-1', outcomeData);

      expect(mockPrisma.connection.update).toHaveBeenCalledWith({
        where: { id: 'conn-1' },
        data: {
          outcomeType: OutcomeType.MEETING_HELD,
          outcomeNotes: 'Great meeting!',
          outcomeReportedAt: expect.any(Date),
          meetingScheduled: true,
          meetingDate: expect.any(Date),
        },
      });
      expect(result.outcomeType).toEqual(OutcomeType.MEETING_HELD);
    });
  });

  describe('getEventNetworkingStats', () => {
    it('should calculate correct networking statistics', async () => {
      const connections = [
        {
          ...mockConnection,
          userA: { id: 'user-a', firstName: 'John', lastName: 'Doe' },
          userB: { id: 'user-b', firstName: 'Jane', lastName: 'Smith' },
          followUpSentAt: new Date(),
          meetingScheduled: true,
        },
        {
          ...mockConnection,
          id: 'conn-2',
          userAId: 'user-a',
          userBId: 'user-c',
          userA: { id: 'user-a', firstName: 'John', lastName: 'Doe' },
          userB: { id: 'user-c', firstName: 'Bob', lastName: 'Wilson' },
          outcomeType: OutcomeType.PARTNERSHIP,
        },
      ];
      mockPrisma.connection.findMany.mockResolvedValue(connections);

      const stats = await service.getEventNetworkingStats('event-1');

      expect(stats.totalConnections).toBe(2);
      expect(stats.uniqueNetworkers).toBe(3); // user-a, user-b, user-c
      expect(stats.followUpsSent).toBe(1);
      expect(stats.meetingsScheduled).toBe(1);
      expect(stats.reportedOutcomes).toBe(1);
      expect(stats.topConnectors[0].userId).toBe('user-a'); // Most connected
      expect(stats.topConnectors[0].connectionCount).toBe(2);
    });
  });

  describe('connectionExists', () => {
    it('should return true if connection exists', async () => {
      mockPrisma.connection.findUnique.mockResolvedValue(mockConnection);

      const exists = await service.connectionExists('user-a', 'user-b', 'event-1');

      expect(exists).toBe(true);
    });

    it('should return false if connection does not exist', async () => {
      mockPrisma.connection.findUnique.mockResolvedValue(null);

      const exists = await service.connectionExists('user-x', 'user-y', 'event-1');

      expect(exists).toBe(false);
    });

    it('should normalize user order when checking', async () => {
      mockPrisma.connection.findUnique.mockResolvedValue(mockConnection);

      await service.connectionExists('user-b', 'user-a', 'event-1');

      expect(mockPrisma.connection.findUnique).toHaveBeenCalledWith({
        where: {
          userAId_userBId_eventId: {
            userAId: 'user-a', // Sorted
            userBId: 'user-b',
            eventId: 'event-1',
          },
        },
      });
    });
  });
});
