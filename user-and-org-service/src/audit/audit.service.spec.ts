import { Test, TestingModule } from '@nestjs/testing';
import { AuditService } from './audit.service';
import { PrismaService } from 'src/prisma.service';

describe('AuditService', () => {
  let service: AuditService;
  let prisma: PrismaService;
  let module: TestingModule; // <-- Add this

  beforeEach(async () => {
    module = await Test.createTestingModule({
      // <-- Add this
      providers: [
        AuditService,
        {
          provide: PrismaService,
          useValue: { auditLog: { create: jest.fn() } },
        },
      ],
    }).compile();

    service = module.get<AuditService>(AuditService);
    prisma = module.get<PrismaService>(PrismaService);
  });

  afterAll(async () => {
    // <-- Add this
    await module.close();
  });

  it('should call prisma.auditLog.create with the correct data', async () => {
    const logData = {
      action: 'USER_LOGIN',
      actingUserId: 'user-123',
      organizationId: 'org-abc',
    };

    await service.log(logData);

    expect(prisma.auditLog.create).toHaveBeenCalledWith({
      data: {
        action: logData.action,
        actingUserId: logData.actingUserId,
        organizationId: logData.organizationId,
        targetUserId: undefined,
        details: undefined,
      },
    });
  });
});
