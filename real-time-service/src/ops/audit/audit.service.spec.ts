import { Test, TestingModule } from '@nestjs/testing';
import { AuditService } from './audit.service';
import { HttpService } from '@nestjs/axios';
import { AuditGateway } from './audit.gateway';
import { of } from 'rxjs';

const mockHttp = { post: jest.fn() };
const mockGateway = { broadcastNewLog: jest.fn() };

describe('AuditService', () => {
  let service: AuditService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuditService,
        { provide: HttpService, useValue: mockHttp },
        { provide: AuditGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<AuditService>(AuditService);
    jest.clearAllMocks();
  });

  it('should save a log and then broadcast it via the gateway', async () => {
    const auditPayload = {
      action: 'USER_LOGIN',
      actingUserId: 'u1',
      organizationId: 'o1',
    };
    const savedLogEntry = {
      id: 'log-1',
      ...auditPayload,
      createdAt: new Date(),
    };
    mockHttp.post.mockReturnValue(
      of({ data: savedLogEntry, status: 201 } as any),
    );

    await service.handleAuditEvent(auditPayload);

    expect(mockHttp.post).toHaveBeenCalled();
    expect(mockGateway.broadcastNewLog).toHaveBeenCalledWith(savedLogEntry);
  });

  it('should NOT broadcast the log if saving it fails', async () => {
    const auditPayload = {
      action: 'USER_LOGIN',
      actingUserId: 'u1',
      organizationId: 'o1',
    };
    mockHttp.post.mockReturnValue(of({ data: null, status: 500 } as any)); // Simulate a failure

    await service.handleAuditEvent(auditPayload);

    expect(mockHttp.post).toHaveBeenCalled();
    expect(mockGateway.broadcastNewLog).not.toHaveBeenCalled();
  });
});
