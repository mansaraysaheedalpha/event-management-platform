//src/invitations/invitation.service.ts
import {
  Injectable,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { randomBytes } from 'crypto';
import * as bcrypt from 'bcrypt';
import { PrismaService } from 'src/prisma.service';
import { MailerService } from '@nestjs-modules/mailer';

interface CreateInvitationData {
  email: string;
  role: string;
  organizationId: string;
  invitedById: string;
}

interface AcceptInvitationData {
  first_name: string;
  last_name: string;
  password: string;
}

@Injectable()
export class InvitationsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly mailerService: MailerService,
  ) {}

  async create(data: CreateInvitationData) {
    const role = await this.prisma.role.findUnique({
      where: {
        name_organizationId: {
          name: data.role,
          organizationId: data.organizationId,
        },
      },
    });
    if (!role)
      throw new NotFoundException(
        `Role '${data.role}' not found in this organization.`,
      );

    const rawToken = randomBytes(32).toString('hex');
    const hashedToken = await bcrypt.hash(rawToken, 10);

    const invitation = await this.prisma.invitation.create({
      data: {
        email: data.email,
        token: hashedToken,
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // expires in 7 days
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
    const invitationUrl = `http://yourapp.com/accept-invitation?token=${rawToken}`;

    await this.mailerService.sendMail({
      to: invitation.email,
      subject: `You're Invited to Join ${invitation.organization.name} on GlobalConnect`,
      html: `
        <h2>You've Been Invited!</h2>
        <p>Hi there,</p>
        <p><strong>${inviterName}</strong> has invited you to join their organization <strong>${invitation.organization.name}</strong> on <strong>GlobalConnect</strong>.</p>
        <p>Click the button below to accept your invitation and create your account:</p>
        <p style="margin: 20px 0;">
          <a href="${invitationUrl}" target="_blank" style="background-color:#4CAF50;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Accept Invitation</a>
        </p>
        <p>This invitation link will expire in <strong>7 days</strong> for your security.</p>
        <p>If you weren't expecting this invitation, you can safely ignore this email.</p>
        <br />
        <p>— The GlobalConnect Team</p>
      `,
    });

    // 4. Return a success message instead of the token
    return {
      message: `Invitation successfully sent to ${invitation.email}.`,
    };
  }

  async accept(token: string, data: AcceptInvitationData) {
    const matchedInvitation = await this.findAndValidateInvitation(token);

    const result = await this.prisma.$transaction(async (tx) => {
      let user = await tx.user.findUnique({
        where: { email: matchedInvitation.email },
      });

      if (!user) {
        const hashedPassword = await bcrypt.hash(data.password, 10);
        user = await tx.user.create({
          data: {
            email: matchedInvitation.email,
            first_name: data.first_name,
            last_name: data.last_name,
            password: hashedPassword,
          },
        });
      }

      const membership = await tx.membership.create({
        data: {
          userId: user.id,
          organizationId: matchedInvitation.organizationId,
          roleId: matchedInvitation.roleId,
        },
        include: { role: true },
      });

      await tx.invitation.delete({ where: { id: matchedInvitation.id } });

      return { user, membership };
    });

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { password, ...safeUser } = result.user;
    return { user: safeUser, membership: result.membership };
  }

  // Helper to ensure the invitation is found and includes the role
  private async findAndValidateInvitation(token: string) {
    const unexpiredInvitations = await this.prisma.invitation.findMany({
      where: { expiresAt: { gte: new Date() } },
      include: { role: true },
    });

    for (const invitation of unexpiredInvitations) {
      const isMatch = await bcrypt.compare(token, invitation.token);
      if (isMatch) return invitation;
    }

    throw new UnauthorizedException('Invalid or expired invitation token.');
  }
}
