// In src/organizations/organizations.service.ts
import {
  BadRequestException,
  ForbiddenException,
  forwardRef,
  Inject,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { CreateNewOrganizationDTO } from './dto/create-new-organization.dto';
import { UpdateOrganizationDTO } from './dto/update-organization.dto';
import { AuditService } from 'src/audit/audit.service';
import { MailerService } from '@nestjs-modules/mailer';
import { randomBytes } from 'crypto';
import { AuthService } from 'src/auth/auth.service';

@Injectable()
export class OrganizationsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly auditService: AuditService,
    private readonly mailerService: MailerService,
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
    return membershipRecord; // This returns the array directly
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
    // Fetches all roles for an organization, excluding the non-assignable OWNER role.
    return this.prisma.role.findMany({
      where: {
        organizationId,
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
    newRoleId: string, // <-- Changed from newRoleName
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

    // **REFINEMENT**: The service now finds the role by ID.
    const newRole = await this.prisma.role.findUnique({
      where: { id: newRoleId, organizationId: orgId }, // Ensure role belongs to the org
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
        // 1. Create the new organization
        const newOrg = await tx.organization.create({
          data: { name: newOrgDto.organization_name },
        });

        // --- THIS IS THE NEW CODE ---
        // 2. Seed the default roles for the new organization
        await tx.role.createMany({
          data: [
            { name: 'ADMIN', organizationId: newOrg.id },
            { name: 'MEMBER', organizationId: newOrg.id },
          ],
        });
        // ----------------------------

        // 3. Find the system-wide OWNER role
        const ownerRole = await tx.role.findFirstOrThrow({
          where: { name: 'OWNER', isSystemRole: true },
        });

        // 4. Assign the creator as the OWNER
        const newMembership = await tx.membership.create({
          data: {
            userId: existingUser.id,
            organizationId: newOrg.id,
            roleId: ownerRole.id,
          },
          include: { role: true },
        });

        return { organization: newOrg, membership: newMembership };
      },
    );
    // NOW, GENERATE FULL TOKENS FOR THE NEWLY CREATED ORG
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
        // This 'some' clause ensures we only find the organization
        // if a membership record exists linking it to the user.
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
    // 1. Verify the user is the owner of the organization.
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

    // 2. Find other organizations the user belongs to BEFORE deleting.
    const otherMemberships = await this.prisma.membership.findMany({
      where: {
        userId: actingUserId,
        organizationId: { not: orgId }, // Exclude the one being deleted
      },
    });

    const nextOrgId =
      otherMemberships.length > 0 ? otherMemberships[0].organizationId : null;

    const orgName = membership.organization.name;
    const userEmail = membership.user.email;

    // 3. Perform either a "force" delete or a "soft" delete
    if (force) {
      await this.prisma.organization.delete({ where: { id: orgId } });
      await this.auditService.log({
        action: 'ORGANIZATION_FORCE_DELETED',
        actingUserId,
        organizationId: orgId,
      });

      try {
        await this.mailerService.sendMail({
          to: userEmail,
          subject: `Your Organization "${orgName}" Has Been Permanently Deleted`,
          html: `<p>This is a confirmation that the organization, <strong>${orgName}</strong>, has been permanently deleted from GlobalConnect. This action cannot be undone.</p>`,
        });
      } catch (error) {
        console.error('Failed to send permanent deletion email:', error);
      }
    } else {
      // --- Soft Delete Logic ---
      if (membership.organization.status === 'PENDING_DELETION') {
        throw new BadRequestException(
          'This organization is already scheduled for deletion.',
        );
      }

      const gracePeriodDays = 7;
      const deletionDate = new Date();
      deletionDate.setDate(deletionDate.getDate() + gracePeriodDays);
      const restoreToken = randomBytes(32).toString('hex');
      const restoreUrl = `http://localhost:3001/organizations/restore/${restoreToken}`;

      await this.prisma.organization.update({
        where: { id: orgId },
        data: {
          status: 'PENDING_DELETION',
          deletionScheduledAt: deletionDate,
          restoreToken: restoreToken,
        },
      });

      await this.auditService.log({
        action: 'ORGANIZATION_DELETION_SCHEDULED',
        actingUserId,
        organizationId: orgId,
        details: { deletionDate },
      });

      try {
        await this.mailerService.sendMail({
          to: userEmail,
          subject: `Your Organization "${orgName}" is Scheduled for Deletion`,
          html: `
          <p>This is a notification that the organization, <strong>${orgName}</strong>, is scheduled to be permanently deleted on ${deletionDate.toLocaleDateString()}.</p>
          <p>If this was a mistake, you can restore your organization by clicking the link below:</p>
          <p><a href="${restoreUrl}">Restore My Organization</a></p>
          <p>This restore link is valid until the deletion date.</p>
        `,
        });
      } catch (error) {
        console.error('Failed to send scheduled deletion email:', error);
      }
    }

    // 4. Return the new intelligent payload
    return { success: true, nextOrganizationId: nextOrgId };
  }

  async restoreOrgFromToken(token: string) {
    const orgToRestore = await this.prisma.organization.findUnique({
      where: { restoreToken: token },
    });

    if (!orgToRestore || orgToRestore.status !== 'PENDING_DELETION') {
      throw new BadRequestException(
        'This restore link is invalid or has expired.',
      );
    }

    await this.prisma.organization.update({
      where: { id: orgToRestore.id },
      data: {
        status: 'ACTIVE',
        deletionScheduledAt: null,
        restoreToken: null, // Invalidate the token after use
      },
    });

    await this.auditService.log({
      action: 'ORGANIZATION_RESTORED_VIA_TOKEN',
      actingUserId: 'SYSTEM', // Or find the owner's ID if needed
      organizationId: orgToRestore.id,
    });

    return {
      message: `Organization "${orgToRestore.name}" has been successfully restored.`,
    };
  }
  // NEW: This method restores an organization
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
