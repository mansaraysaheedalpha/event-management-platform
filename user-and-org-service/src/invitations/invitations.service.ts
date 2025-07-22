import { Injectable, UnauthorizedException } from '@nestjs/common';
import { randomBytes } from 'crypto';
import * as bcrypt from 'bcrypt';
import { PrismaService } from 'src/prisma.service';
import { Role } from '@prisma/client';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { MailerService } from '@nestjs-modules/mailer';

interface CreateInvitationData {
  email: string;
  role: Role;
  organizationId: string;
  invitedById: string;
}

interface AcceptInvitationData {
  first_name: string;
  last_name: string;
  password: string;
}

interface Invitation {
  id: string;
  email: string;
  token: string;
  role: Role;
  expiresAt: Date;
  createdAt: Date;
  organizationId: string;
  invitedById: string;
}

@Injectable()
export class InvitationsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly mailerService: MailerService,
  ) {}

  async create(data: CreateInvitationData) {
    // 1. Generate a secure random token
    const rawToken = randomBytes(32).toString('hex');

    // 2. Hash it before saving to the DB
    const hashedToken = await bcrypt.hash(rawToken, 10);

    // 3. Save invitation in the DB
    const invitation = await this.prisma.invitation.create({
      data: {
        email: data.email,
        token: hashedToken,
        role: data.role,
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // expires in 7 days
        organization: {
          connect: { id: data.organizationId },
        },
        invitedBy: {
          connect: { id: data.invitedById },
        },
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
    // 1. Find all non-expired invitations.
    const unexpiredInvitations = await this.prisma.invitation.findMany({
      where: {
        expiresAt: { gte: new Date() },
      },
    });

    if (!unexpiredInvitations.length) {
      throw new UnauthorizedException('Invalid or expired invitation token.');
    }

    // 2. Find the specific invitation that matches the provided token.
    let matchedInvitation: Invitation | null = null;
    for (const invitation of unexpiredInvitations) {
      const isMatch = await bcrypt.compare(token, invitation.token);
      if (isMatch) {
        matchedInvitation = invitation;
        break;
      }
    }

    if (!matchedInvitation) {
      throw new UnauthorizedException('Invalid or expired invitation token.');
    }

    // Now we know the token is valid and we have the correct invitation record.
    // The rest of your logic was nearly perfect.

    const result = await this.prisma.$transaction(async (tx) => {
      // 3. Check if user already exists, or create them.
      let user = await tx.user.findUnique({
        where: { email: matchedInvitation.email },
      });

      if (!user) {
        // User does not exist, create them.
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

      // 4. Create the membership link.
      await tx.membership.create({
        data: {
          userId: user.id,
          organizationId: matchedInvitation.organizationId,
          role: matchedInvitation.role,
        },
      });

      // 5. Delete the invitation so it cannot be used again.
      await tx.invitation.delete({
        where: { id: matchedInvitation.id },
      });

      return { user };
    });
    const user = result;
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { password, ...safeUser } = user.user;

    return safeUser;
  }
}
