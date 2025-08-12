// In src/organizations/organizations.service.ts
import {
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { Role } from '@prisma/client';
import { PrismaService } from 'src/prisma.service';
import { CreateNewOrganizationDTO } from './dto/create-new-organization.dto';
import { UpdateOrganizationDTO } from './dto/update-organization.dto';
import { AuditService } from 'src/audit/audit.service';

@Injectable()
export class OrganizationsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly auditService: AuditService,
  ) {}

  async listMembers(organizationId: string) {
    const membershipRecord = await this.prisma.membership.findMany({
      where: { organizationId },
      include: {
        user: {
          select: {
            id: true,
            email: true,
            first_name: true,
            last_name: true,
          },
        },
      },
    });
    return { membershipRecord };
  }

  async removeMember(
    orgId: string,
    memberToRemoveId: string,
    actingUserId: string,
  ) {
    await this.prisma.membership.delete({
      where: {
        userId_organizationId: {
          userId: memberToRemoveId,
          organizationId: orgId,
        },
      },
    });

    await this.auditService.log({
      action: 'MEMBER_REMOVED',
      organizationId: orgId,
      actingUserId,
      targetUserId: memberToRemoveId,
    });
  }

  async updateMemberRole(
    orgId: string,
    userId: string,
    newRoleName: string,
    actingUserId: string,
  ) {
    const membership = await this.prisma.membership.findUniqueOrThrow({
      where: {
        userId_organizationId: {
          userId,
          organizationId: orgId,
        },
      },
      include: { role: true },
    });

    if (membership.role.name === 'OWNER') {
      throw new ForbiddenException(
        'Cannot change the role of an organization owner.',
      );
    }

    const newRole = await this.prisma.role.findUnique({
      where: {
        name_organizationId: { name: newRoleName, organizationId: orgId },
      },
    });
    if (!newRole) throw new NotFoundException(`Role  not found.`);

    await this.prisma.membership.update({
      where: {
        userId_organizationId: {
          userId,
          organizationId: orgId,
        },
      },
      data: {
        role: { connect: { id: newRole.id } },
      },
    });

    await this.auditService.log({
      action: 'MEMBER_ROLE_UPDATED',
      organizationId: orgId,
      actingUserId,
      targetUserId: userId,
      details: { newRole: newRole },
    });
    return { message: 'Role updated successfully' };
  }

  async userOrganizations(userId: string) {
    const memberships = await this.prisma.membership.findMany({
      where: { userId },
      include: {
        organization: {
          select: {
            id: true,
            name: true,
            createdAt: true,
          },
        },
      },
    });

    if (!memberships || memberships.length === 0) {
      return [];
    }

    return memberships.map((membership) => membership.organization);
  }

  async createNewOrganization(
    userId: string,
    newOrgDto: CreateNewOrganizationDTO,
  ) {
    const existingUser = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });

    const result = await this.prisma.$transaction(async (tx) => {
      const newOrg = await tx.organization.create({
        data: {
          name: newOrgDto.organization_name,
        },
      });

      const ownerRole = await tx.role.findFirst({
        where: { name: 'OWNER', isSystemRole: true },
      });
      if (!ownerRole)
        throw new Error(
          'System role OWNER not found. Please seed the database.',
        );

      await tx.membership.create({
        data: {
          userId: existingUser.id,
          organizationId: newOrg.id,
          roleId: ownerRole.id,
        },
      });

      return { organization: newOrg };
    });
    return result;
  }

  async findOrg(orgId: string) {
    const organizationDetails =
      await this.prisma.organization.findUniqueOrThrow({
        where: { id: orgId },
      });
    return { organizationDetails };
  }

  async updateOrgDetails(orgId: string, data: UpdateOrganizationDTO) {
    await this.prisma.organization.update({
      where: { id: orgId },
      data: {
        ...data,
      },
    });
  }

  async deleteOrg(orgId: string) {
    await this.prisma.organization.delete({
      where: { id: orgId },
    });
  }
}
