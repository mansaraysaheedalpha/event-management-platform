import { Test, TestingModule } from '@nestjs/testing';
import { OrganizationsService } from './organizations.service';
import { PrismaService } from 'src/prisma.service';
import { AuditService } from 'src/audit/audit.service';
import { ForbiddenException, NotFoundException } from '@nestjs/common';

describe('OrganizationsService', () => {
  let service: OrganizationsService;
  let prisma: PrismaService;
  let auditService: AuditService;
  let module: TestingModule;

  const mockMembership = {
    userId: 'user-to-update',
    organizationId: 'org-1',
    role: { name: 'MEMBER' },
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        OrganizationsService,
        {
          provide: PrismaService,
          useValue: {
            membership: {
              findUniqueOrThrow: jest.fn(),
              update: jest.fn(),
              delete: jest.fn(),
            },
            role: { findUnique: jest.fn() },
          },
        },
        { provide: AuditService, useValue: { log: jest.fn() } },
      ],
    }).compile();

    service = module.get<OrganizationsService>(OrganizationsService);
    prisma = module.get<PrismaService>(PrismaService);
    auditService = module.get<AuditService>(AuditService);
  });

  afterAll(async () => {
    await module.close();
  });

  describe('updateMemberRole', () => {
    it('should successfully update a member role', async () => {
      jest
        .spyOn(prisma.membership, 'findUniqueOrThrow')
        .mockResolvedValue(mockMembership as any);
      jest
        .spyOn(prisma.role, 'findUnique')
        .mockResolvedValue({ id: 'new-role-id', name: 'ADMIN' } as any);

      await service.updateMemberRole(
        'org-1',
        'user-to-update',
        'ADMIN',
        'acting-admin-id',
      );

      expect(prisma.membership.update).toHaveBeenCalled();
      expect(auditService.log).toHaveBeenCalled();
    });

    it('should throw ForbiddenException when trying to change the role of an OWNER', async () => {
      const ownerMembership = { ...mockMembership, role: { name: 'OWNER' } };
      jest
        .spyOn(prisma.membership, 'findUniqueOrThrow')
        .mockResolvedValue(ownerMembership as any);

      await expect(
        service.updateMemberRole(
          'org-1',
          'user-to-update',
          'ADMIN',
          'acting-admin-id',
        ),
      ).rejects.toThrow(ForbiddenException);
    });

    it('should throw NotFoundException if the new role does not exist', async () => {
      jest
        .spyOn(prisma.membership, 'findUniqueOrThrow')
        .mockResolvedValue(mockMembership as any);
      jest.spyOn(prisma.role, 'findUnique').mockResolvedValue(null); // Role not found

      await expect(
        service.updateMemberRole(
          'org-1',
          'user-to-update',
          'FAKE_ROLE',
          'acting-admin-id',
        ),
      ).rejects.toThrow(NotFoundException);
    });
  });
});
