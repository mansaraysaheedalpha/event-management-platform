// src/invitations/invitations.service.ts
import {
  Injectable,
  NotFoundException,
  UnauthorizedException,
  ConflictException,
  BadRequestException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { randomBytes } from 'crypto';
import * as bcrypt from 'bcrypt';
import { PrismaService } from 'src/prisma.service';
import { EmailService } from 'src/email/email.service';
import { InvitationPreviewResponseDTO } from './dto/InvitationPreviewDTO';

interface CreateInvitationData {
  email: string;
  role: string;
  organizationId: string;
  invitedById: string;
}

interface AcceptInvitationNewUserData {
  first_name: string;
  last_name: string;
  password: string;
}

interface AcceptInvitationExistingUserData {
  password: string;
}

@Injectable()
export class InvitationsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly emailService: EmailService,
    private readonly configService: ConfigService,
  ) {}

  async create(data: CreateInvitationData) {
    // Look for org-specific role first, then fall back to system role
    const role = await this.prisma.role.findFirst({
      where: {
        name: data.role,
        OR: [
          { organizationId: data.organizationId },  // Org-specific role
          { isSystemRole: true },                   // System role
        ],
      },
    });
    if (!role)
      throw new NotFoundException(
        `Role '${data.role}' not found.`,
      );

    const rawToken = randomBytes(32).toString('hex');
    const hashedToken = await bcrypt.hash(rawToken, 10);

    const invitation = await this.prisma.invitation.create({
      data: {
        email: data.email,
        token: hashedToken,
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
        organization: {
          connect: { id: data.organizationId },
        },
        invitedBy: {
          connect: { id: data.invitedById },
        },
        role: { connect: { id: role.id } },
      },
      include: {
        organization: true,
        invitedBy: {
          select: {
            first_name: true,
            last_name: true,
          },
        },
      },
    });

    const inviterName = `${invitation.invitedBy.first_name} ${invitation.invitedBy.last_name}`;
    // Handle comma-separated FRONTEND_URL (take first one for email links)
    const frontendUrl = (this.configService.get('FRONTEND_URL') || '').split(',')[0].trim();
    const invitationUrl = `${frontendUrl}/accept-invitation?token=${rawToken}`;

    await this.emailService.sendInvitationEmail(
      invitation.email,
      inviterName,
      invitation.organization.name,
      invitationUrl,
      role.name, // Include role name in email so invitee knows their assigned role
    );

    return {
      message: `Invitation successfully sent to ${invitation.email}.`,
    };
  }

  /**
   * Preview an invitation before acceptance.
   * Returns invitation details and whether the user already exists.
   * Frontend uses this to show the appropriate form (new user vs existing user).
   */
  async preview(token: string): Promise<InvitationPreviewResponseDTO> {
    const invitation = await this.findAndValidateInvitation(token);

    // Check if user already exists
    const existingUser = await this.prisma.user.findUnique({
      where: { email: invitation.email },
      select: { first_name: true },
    });

    // Get organization and inviter details
    const invitationDetails = await this.prisma.invitation.findUnique({
      where: { id: invitation.id },
      include: {
        organization: { select: { name: true } },
        invitedBy: { select: { first_name: true, last_name: true } },
        role: { select: { name: true } },
      },
    });

    return {
      email: invitation.email,
      organizationName: invitationDetails.organization.name,
      inviterName: `${invitationDetails.invitedBy.first_name} ${invitationDetails.invitedBy.last_name}`,
      roleName: invitationDetails.role.name,
      userExists: !!existingUser,
      existingUserFirstName: existingUser?.first_name,
      expiresAt: invitation.expiresAt,
    };
  }

  /**
   * Accept invitation as a NEW user (no existing account).
   * Creates a new user account and adds them to the organization.
   */
  async acceptAsNewUser(token: string, data: AcceptInvitationNewUserData) {
    const matchedInvitation = await this.findAndValidateInvitation(token);

    // Verify user doesn't already exist
    const existingUser = await this.prisma.user.findUnique({
      where: { email: matchedInvitation.email },
    });

    if (existingUser) {
      throw new ConflictException(
        'An account already exists for this email. Please use the existing user acceptance flow.',
      );
    }

    const result = await this.prisma.$transaction(async (tx) => {
      const hashedPassword = await bcrypt.hash(data.password, 10);
      const user = await tx.user.create({
        data: {
          email: matchedInvitation.email,
          first_name: data.first_name,
          last_name: data.last_name,
          password: hashedPassword,
        },
      });

      const membership = await tx.membership.create({
        data: {
          userId: user.id,
          organizationId: matchedInvitation.organizationId,
          roleId: matchedInvitation.roleId,
        },
        include: {
          role: {
            include: {
              permissions: true,
            },
          },
        },
      });

      await tx.invitation.delete({ where: { id: matchedInvitation.id } });

      return { user, membership };
    });

    const { password, ...safeUser } = result.user;
    return { user: safeUser, membership: result.membership };
  }

  /**
   * Accept invitation as an EXISTING user.
   * Requires password authentication to prove account ownership.
   * This prevents unauthorized users from adding someone to an org without consent.
   */
  async acceptAsExistingUser(
    token: string,
    data: AcceptInvitationExistingUserData,
  ) {
    const matchedInvitation = await this.findAndValidateInvitation(token);

    // Find existing user
    const existingUser = await this.prisma.user.findUnique({
      where: { email: matchedInvitation.email },
    });

    if (!existingUser) {
      throw new BadRequestException(
        'No account exists for this email. Please use the new user registration flow.',
      );
    }

    // Authenticate: verify password matches existing account
    const passwordValid = await bcrypt.compare(
      data.password,
      existingUser.password,
    );

    if (!passwordValid) {
      throw new UnauthorizedException(
        'Invalid password. Please enter your existing account password to accept this invitation.',
      );
    }

    // Check if user is already a member of this organization
    const existingMembership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: {
          userId: existingUser.id,
          organizationId: matchedInvitation.organizationId,
        },
      },
    });

    if (existingMembership) {
      // Clean up the invitation since user is already a member
      await this.prisma.invitation.delete({
        where: { id: matchedInvitation.id },
      });
      throw new ConflictException(
        'You are already a member of this organization.',
      );
    }

    const result = await this.prisma.$transaction(async (tx) => {
      const membership = await tx.membership.create({
        data: {
          userId: existingUser.id,
          organizationId: matchedInvitation.organizationId,
          roleId: matchedInvitation.roleId,
        },
        include: {
          role: {
            include: {
              permissions: true,
            },
          },
        },
      });

      await tx.invitation.delete({ where: { id: matchedInvitation.id } });

      return { user: existingUser, membership };
    });

    const { password, ...safeUser } = result.user;
    return { user: safeUser, membership: result.membership };
  }

  /**
   * @deprecated Use acceptAsNewUser or acceptAsExistingUser instead.
   * Kept for backward compatibility but will be removed in future versions.
   */
  async accept(token: string, data: AcceptInvitationNewUserData) {
    // Determine if user exists and route to appropriate method
    const matchedInvitation = await this.findAndValidateInvitation(token);
    const existingUser = await this.prisma.user.findUnique({
      where: { email: matchedInvitation.email },
    });

    if (existingUser) {
      // For backwards compatibility, attempt to authenticate with provided password
      return this.acceptAsExistingUser(token, { password: data.password });
    }

    return this.acceptAsNewUser(token, data);
  }

  // Timing-safe: always iterate through ALL invitations without early exit
  private async findAndValidateInvitation(token: string) {
    const unexpiredInvitations = await this.prisma.invitation.findMany({
      where: { expiresAt: { gte: new Date() } },
      include: { role: true },
    });

    let matchedInvitation = null;
    for (const invitation of unexpiredInvitations) {
      const isMatch = await bcrypt.compare(token, invitation.token);
      if (isMatch && !matchedInvitation) {
        matchedInvitation = invitation;
        // Continue iterating to prevent timing attacks
      }
    }

    if (!matchedInvitation) {
      throw new UnauthorizedException('Invalid or expired invitation token.');
    }

    return matchedInvitation;
  }
}
