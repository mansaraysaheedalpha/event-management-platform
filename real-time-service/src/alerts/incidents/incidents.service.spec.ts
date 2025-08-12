import { Test, TestingModule } from '@nestjs/testing';
import { IncidentsService } from './incidents.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { IncidentsGateway } from './incident.gateway';
import { ForbiddenException } from '@nestjs/common';
import { IncidentUpdateStatus } from './dto/update-incidents.dto';
import { IncidentType, IncidentSeverity } from './dto/report-incident.dto';

// Mocks
const mockPrisma = {
  incident: { create: jest.fn(), findUnique: jest.fn(), update: jest.fn() },
  chatSession: { findUnique: jest.fn() },
};
const mockIdempotency = { checkAndSet: jest.fn() };
const mockRedis = { get: jest.fn(), set: jest.fn(), publish: jest.fn() };
const mockGateway = {
  broadcastNewIncident: jest.fn(),
  broadcastIncidentUpdate: jest.fn(),
};

// Data
const mockReporter = { id: 'user-reporter-1' };
const mockAdmin = { id: 'user-admin-1', orgId: 'org-1' };
const mockSession = {
  id: 'session-1',
  eventId: 'event-1',
  organizationId: 'org-1',
};
// **FIX**: Correctly spread the object and then set the ID to avoid overwrite.
const mockIncident = { ...mockSession, id: 'incident-1' };

describe('IncidentsService', () => {
  let service: IncidentsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        IncidentsService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: IdempotencyService, useValue: mockIdempotency },
        { provide: REDIS_CLIENT, useValue: mockRedis },
        { provide: IncidentsGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<IncidentsService>(IncidentsService);
    jest.clearAllMocks();
  });

  describe('reportIncident', () => {
    // **FIX**: Use the imported enums for strong typing.
    const reportDto = {
      type: IncidentType.TECHNICAL,
      severity: IncidentSeverity.LOW,
      details: 'The microphone is not working.',
      idempotencyKey: 'k1',
    };

    it('should create an incident and broadcast it via the gateway', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      mockRedis.get.mockResolvedValue(null);
      mockPrisma.chatSession.findUnique.mockResolvedValue(mockSession);
      mockPrisma.incident.create.mockResolvedValue(mockIncident);

      await service.reportIncident(mockReporter.id, mockSession.id, reportDto);

      expect(mockPrisma.incident.create).toHaveBeenCalled();
      expect(mockRedis.publish).toHaveBeenCalledWith(
        'audit-events',
        expect.any(String),
      );
      expect(mockGateway.broadcastNewIncident).toHaveBeenCalledWith(
        mockIncident,
      );
    });
  });

  describe('updateIncidentStatus', () => {
    // **FIX**: Use the imported enum for strong typing.
    const updateDto = {
      incidentId: 'incident-1',
      status: IncidentUpdateStatus.ACKNOWLEDGED,
      idempotencyKey: 'k2',
    };

    it('should update an incident and broadcast the update', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      mockPrisma.incident.findUnique.mockResolvedValue(mockIncident);
      mockPrisma.incident.update.mockResolvedValue({
        ...mockIncident,
        status: 'ACKNOWLEDGED',
      });

      await service.updateIncidentStatus(
        mockAdmin.id,
        mockAdmin.orgId,
        updateDto,
      );

      expect(mockPrisma.incident.update).toHaveBeenCalled();
      expect(mockGateway.broadcastIncidentUpdate).toHaveBeenCalled();
    });

    it('should throw ForbiddenException if admin org does not match incident org', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      mockPrisma.incident.findUnique.mockResolvedValue(mockIncident);

      const otherOrgId = 'org-2';
      await expect(
        service.updateIncidentStatus(mockAdmin.id, otherOrgId, updateDto),
      ).rejects.toThrow(ForbiddenException);
    });
  });
});
