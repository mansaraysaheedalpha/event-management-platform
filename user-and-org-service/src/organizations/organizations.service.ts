// src/organizations/organizations.service.ts
import {
  BadRequestException,
  ForbiddenException,
  forwardRef,
  Inject,
  Injectable,
  NotFoundException,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcrypt';
import { PrismaService } from 'src/prisma.service';
import { CreateNewOrganizationDTO } from './dto/create-new-organization.dto';
import { UpdateOrganizationDTO } from './dto/update-organization.dto';
import { AuditService } from 'src/audit/audit.service';
import { EmailService } from 'src/email/email.service';
import { randomBytes } from 'crypto';
import { AuthService } from 'src/auth/auth.service';

@Injectable()
export class OrganizationsService {
  private readonly logger = new Logger(OrganizationsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly auditService: AuditService,
    private readonly emailService: EmailService,
    private readonly configService: ConfigService,
    @Inject(forwardRef(() => AuthService))
    private readonly authService: AuthService,
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
            imageUrl: true,
          },
        },
        role: {
          select: {
            id: true,
            name: true,
          },
        },
      },
    });
    return membershipRecord;
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

  async getRoles(organizationId: string) {
    return this.prisma.role.findMany({
      where: {
        OR: [
          { organizationId },           // Org-specific roles
          { isSystemRole: true },       // System roles (shared by all orgs)
        ],
        name: {
          not: 'OWNER',
        },
      },
    });
  }

  async findRoleById(id: string) {
    return this.prisma.role.findUniqueOrThrow({ where: { id } });
  }
  async updateMemberRole(
    orgId: string,
    userId: string,
    newRoleId: string,
    actingUserId: string,
  ) {
    const membership = await this.prisma.membership.findUniqueOrThrow({
      where: { userId_organizationId: { userId, organizationId: orgId } },
      include: { role: true },
    });

    if (membership.role.name === 'OWNER') {
      throw new ForbiddenException(
        'Cannot change the role of an organization owner.',
      );
    }

    const newRole = await this.prisma.role.findUnique({
      where: { id: newRoleId, organizationId: orgId },
    });
    if (!newRole) {
      throw new NotFoundException(
        `Role with ID ${newRoleId} not found in this organization.`,
      );
    }

    await this.prisma.membership.update({
      where: { userId_organizationId: { userId, organizationId: orgId } },
      data: { role: { connect: { id: newRole.id } } },
    });

    await this.auditService.log({
      action: 'MEMBER_ROLE_UPDATED',
      organizationId: orgId,
      actingUserId,
      targetUserId: userId,
      details: { oldRole: membership.role.name, newRole: newRole.name },
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

    const { organization, membership } = await this.prisma.$transaction(
      async (tx) => {
        const newOrg = await tx.organization.create({
          data: { name: newOrgDto.organization_name },
        });

        await tx.role.createMany({
          data: [
            { name: 'ADMIN', organizationId: newOrg.id },
            { name: 'MEMBER', organizationId: newOrg.id },
          ],
        });

        const ownerRole = await tx.role.findFirstOrThrow({
          where: { name: 'OWNER', isSystemRole: true },
        });

        const newMembership = await tx.membership.create({
          data: {
            userId: existingUser.id,
            organizationId: newOrg.id,
            roleId: ownerRole.id,
          },
          include: {
            role: {
              include: {
                permissions: true,
              },
            },
          },
        });

        return { organization: newOrg, membership: newMembership };
      },
    );
    const tokens = await this.authService.getTokensForUser(
      existingUser,
      membership,
    );

    return { organization, user: existingUser, tokens };
  }

  async findOrgForUser(orgId: string, userId: string) {
    const organization = await this.prisma.organization.findFirst({
      where: {
        id: orgId,
        members: {
          some: {
            userId: userId,
          },
        },
      },
    });

    if (!organization) {
      throw new ForbiddenException(
        'Organization not found or you do not have access.',
      );
    }

    return organization;
  }

  async findOrg(orgId: string) {
    return this.prisma.organization.findUniqueOrThrow({
      where: { id: orgId },
    });
  }

  async updateOrgDetails(
    orgId: string,
    data: UpdateOrganizationDTO,
    actingUserId: string,
  ) {
    const membership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: { userId: actingUserId, organizationId: orgId },
      },
      include: { role: true },
    });

    if (!membership || !['OWNER', 'ADMIN'].includes(membership.role.name)) {
      throw new ForbiddenException(
        'You do not have permission to update this organization.',
      );
    }

    const updatedOrg = await this.prisma.organization.update({
      where: { id: orgId },
      data: { name: data.name },
    });

    await this.auditService.log({
      action: 'ORGANIZATION_UPDATED',
      actingUserId,
      organizationId: orgId,
      details: { changes: { name: updatedOrg.name } },
    });

    return updatedOrg;
  }

  async deleteOrg(orgId: string, actingUserId: string, force = false) {
    const membership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: { userId: actingUserId, organizationId: orgId },
      },
      include: { role: true, organization: true, user: true },
    });

    if (!membership || membership.role.name !== 'OWNER') {
      throw new ForbiddenException(
        'You do not have permission to delete this organization.',
      );
    }

    const otherMemberships = await this.prisma.membership.findMany({
      where: {
        userId: actingUserId,
        organizationId: { not: orgId },
      },
    });

    const nextOrgId =
      otherMemberships.length > 0 ? otherMemberships[0].organizationId : null;

    const orgName = membership.organization.name;
    const userEmail = membership.user.email;

    if (force) {
      await this.prisma.organization.delete({ where: { id: orgId } });
      await this.auditService.log({
        action: 'ORGANIZATION_FORCE_DELETED',
        actingUserId,
        organizationId: orgId,
      });

      try {
        await this.emailService.sendOrgPermanentlyDeletedEmail(userEmail, orgName);
      } catch (error) {
        this.logger.error('Failed to send permanent deletion email', error);
      }
    } else {
      if (membership.organization.status === 'PENDING_DELETION') {
        throw new BadRequestException(
          'This organization is already scheduled for deletion.',
        );
      }

      const gracePeriodDays = 7;
      const deletionDate = new Date();
      deletionDate.setDate(deletionDate.getDate() + gracePeriodDays);
      const rawRestoreToken = randomBytes(32).toString('hex');
      const hashedRestoreToken = await bcrypt.hash(rawRestoreToken, 10);
      const restoreUrl = `${this.configService.get('API_BASE_URL')}/organizations/restore/${rawRestoreToken}`;

      await this.prisma.organization.update({
        where: { id: orgId },
        data: {
          status: 'PENDING_DELETION',
          deletionScheduledAt: deletionDate,
          restoreToken: hashedRestoreToken,
        },
      });

      await this.auditService.log({
        action: 'ORGANIZATION_DELETION_SCHEDULED',
        actingUserId,
        organizationId: orgId,
        details: { deletionDate },
      });

      try {
        await this.emailService.sendOrgDeletionScheduledEmail(
          userEmail,
          orgName,
          deletionDate,
          restoreUrl,
        );
      } catch (error) {
        this.logger.error('Failed to send scheduled deletion email', error);
      }
    }

    return { success: true, nextOrganizationId: nextOrgId };
  }

  async restoreOrgFromToken(token: string) {
    // Find all orgs pending deletion and compare tokens securely
    const pendingOrgs = await this.prisma.organization.findMany({
      where: { 
        status: 'PENDING_DELETION',
        restoreToken: { not: null },
      },
    });

    let orgToRestore = null;
    for (const org of pendingOrgs) {
      if (org.restoreToken) {
        const isMatch = await bcrypt.compare(token, org.restoreToken);
        if (isMatch && !orgToRestore) {
          orgToRestore = org;
          // Continue iterating to prevent timing attacks
        }
      }
    }

    if (!orgToRestore) {
      throw new BadRequestException(
        'This restore link is invalid or has expired.',
      );
    }

    await this.prisma.organization.update({
      where: { id: orgToRestore.id },
      data: {
        status: 'ACTIVE',
        deletionScheduledAt: null,
        restoreToken: null,
      },
    });

    await this.auditService.log({
      action: 'ORGANIZATION_RESTORED_VIA_TOKEN',
      actingUserId: 'SYSTEM',
      organizationId: orgToRestore.id,
    });

    return {
      message: `Organization "${orgToRestore.name}" has been successfully restored.`,
    };
  }

  async restoreOrg(orgId: string, actingUserId: string) {
    const membership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: {
          userId: actingUserId,
          organizationId: orgId,
        },
      },
      include: { role: true, organization: true },
    });

    if (!membership || membership.role.name !== 'OWNER') {
      throw new ForbiddenException(
        'You do not have permission to restore this organization.',
      );
    }

    if (membership.organization.status !== 'PENDING_DELETION') {
      throw new BadRequestException(
        'This organization is not scheduled for deletion.',
      );
    }

    const updatedOrg = await this.prisma.organization.update({
      where: { id: orgId },
      data: {
        status: 'ACTIVE',
        deletionScheduledAt: null,
      },
    });

    await this.auditService.log({
      action: 'ORGANIZATION_RESTORED',
      actingUserId,
      organizationId: orgId,
    });

    return updatedOrg;
  }
}