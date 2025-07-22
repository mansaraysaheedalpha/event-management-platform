//src/auth/.auth.service.ts
import {
  ForbiddenException,
  Injectable,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { LoginDTO } from './dto/login.dto';
import * as bcrypt from 'bcrypt';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { randomBytes } from 'crypto';
import { MailerService } from '@nestjs-modules/mailer';
import { TwoFactorService } from 'src/two-factor/two-factor.service';
import { AuditService } from 'src/audit/audit.service';
import { PermissionsService } from 'src/permissions/permissions.service';
import { Role } from '@prisma/client';

interface Token {
  id: string;
  hashedResetToken: string;
  userId: string;
  expiresAt: Date;
}

type LoginResponse =
  | { requires2FA: true; userId: string }
  | { requires2FA?: false; access_token: string; refresh_token: string };

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly mailerService: MailerService,
    private twoFactorService: TwoFactorService,
    private auditService: AuditService,
    private readonly permissionsService: PermissionsService,
  ) {}

  async login(loginDTO: LoginDTO): Promise<LoginResponse> {
    const existingUser = await this.prisma.user.findUnique({
      where: { email: loginDTO.email },
      include: {
        memberships: {
          select: {
            organizationId: true,
            role: true,
          },
        },
      },
    });

    if (!existingUser) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const isMatch = await bcrypt.compare(
      loginDTO.password,
      existingUser.password,
    );

    if (!isMatch) {
      throw new UnauthorizedException('Invalid credentials');
    }

    if (existingUser.isTwoFactorEnabled) {
      return {
        requires2FA: true,
        userId: existingUser.id,
      };
    }

    const defaultMembership = existingUser.memberships[0];
    if (!defaultMembership) {
      throw new ForbiddenException('You are not a member of any organization.');
    }

    await this.auditService.log({
      action: 'USER_LOGIN',
      actingUserId: existingUser.id,
      organizationId: defaultMembership.organizationId,
    });
    // Pass the user and their default membership to get tokens
    return await this.getTokensForUser(existingUser, defaultMembership);
  }

  async login2FA(userId: string, twoFactorCode: string) {
    // The only change is adding the 'include' for the role object here
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
      include: {
        memberships: {
          include: {
            role: true,
          },
        },
      },
    });

    const isCodeValid = await this.twoFactorService.is2FACodeValid(
      userId,
      twoFactorCode,
    );

    if (!isCodeValid) {
      throw new UnauthorizedException('Invalid 2FA code.');
    }

    const defaultMembership = user.memberships[0];
    if (!defaultMembership) {
      throw new ForbiddenException('You are not a member of any organization.');
    }

    await this.auditService.log({
      action: 'USER_LOGIN_2FA_SUCCESS',
      actingUserId: user.id,
      organizationId: defaultMembership.organizationId,
    });

    return this.getTokensForUser(user, defaultMembership);
  }

  async logout(userId: string) {
    await this.prisma.user.update({
      where: { id: userId },
      data: { hashedRefreshToken: null },
    });

    await this.auditService.log({
      action: 'USER_LOGOUT',
      actingUserId: userId,
    });
  }

  async refreshTokenService(userId: string, incomingRefreshToken: string) {
    // The only change is adding the 'include' for the role object here
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      include: {
        memberships: {
          include: {
            role: true,
          },
        },
      },
    });

    if (!user || !user.hashedRefreshToken || !user.memberships.length) {
      throw new ForbiddenException('Access Denied');
    }

    const payload = this.jwtService.decode(incomingRefreshToken) as {
      jti: string;
      orgId: string;
    };
    const refreshTokenId = payload.jti;

    const isRefreshTokenMatch = await bcrypt.compare(
      refreshTokenId,
      user.hashedRefreshToken,
    );

    if (!isRefreshTokenMatch) {
      await this.prisma.user.update({
        where: { id: userId },
        data: { hashedRefreshToken: null },
      });
      throw new ForbiddenException('Access Denied: Refresh token mismatch.');
    }

    const relevantMembership =
      user.memberships.find((m) => m.organizationId === payload.orgId) ||
      user.memberships[0];

    return this.getTokensForUser(user, relevantMembership);
  }

  async handlePasswordResetRequest(email: string) {
    const user = await this.prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      // Silently return to prevent attackers from knowing if an email exists.
      return {
        message:
          'If an account with this email exists, a password reset link has been sent.',
      };
    }

    await this.prisma.passwordResetToken.deleteMany({
      where: { userId: user.id },
    });

    const rawResetToken = randomBytes(32).toString('hex');
    const salt = await bcrypt.genSalt(10);
    const hashedResetToken = await bcrypt.hash(rawResetToken, salt);

    await this.prisma.passwordResetToken.create({
      data: {
        hashedResetToken,
        userId: user.id,
        expiresAt: new Date(Date.now() + 15 * 60 * 1000),
      },
    });

    const resetUrl = `https://yourapp.com/reset-password?token=${rawResetToken}`;

    await this.mailerService.sendMail({
      to: user.email,
      subject: `Reset Your Password - GlobalConnect`,
      html: `
        <h2>Password Reset Request</h2>
        <p>Hi ${user.first_name || 'there'},</p>
        <p>We received a request to reset your password for your <strong>GlobalConnect</strong> account.</p>
        <p>Click the link below to set a new password:</p>
        <p><a href="${resetUrl}" target="_blank">Reset My Password</a></p>
        <p>This link will expire in 15 minutes for your security.</p>
        <p>If you didn't request a password reset, please ignore this email or contact support.</p>
        <br />
        <p>— The GlobalConnect Team</p>
      `,
    });

    return {
      message:
        'If an account with this email exists, a password reset link has been sent.',
    };
  }

  async getTokensForUser(
    user: { id: string; email: string },
    membership: {
      organizationId: string;
      role: Role;
    },
  ) {
    // 1. Generate a secure, random string to act as the core refresh token value.
    const refreshTokenId = randomBytes(32).toString('hex');

    // Fetch all permissions for the given role
    const roleWithPermissions = await this.prisma.role.findUnique({
      where: { id: membership.role.id },
      include: { permissions: { select: { name: true } } },
    });

    const permissions =
      roleWithPermissions?.permissions.map((p) => p.name) || [];

    const accessTokenPayload = {
      sub: user.id,
      email: user.email,
      orgId: membership.organizationId,
      role: membership.role.name,
      permissions: permissions, // // <-- Permissions are now dynamically fetched and added
      preferredLanguage: 
    };

    const refreshTokenPayload = {
      sub: user.id,
      jti: refreshTokenId, // "JWT ID", we embed our random string here.
      orgId: membership.organizationId, // Include orgId to maintain context on refresh
    };

    // 3. Sign both tokens with their respective secrets and expirations.
    const accessToken = this.jwtService.sign(accessTokenPayload, {
      secret: this.configService.get<string>('JWT_SECRET'),
      expiresIn: '15m',
    });

    const refreshToken = this.jwtService.sign(refreshTokenPayload, {
      secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
      expiresIn: '7d',
    });

    // 4. Hash the standalone random string, NOT the whole JWT.
    const hashedRefreshToken = await bcrypt.hash(refreshTokenId, 10);

    // 5. Update the database with the new hash.
    await this.prisma.user.update({
      where: { id: user.id },
      data: { hashedRefreshToken: hashedRefreshToken },
    });

    return { access_token: accessToken, refresh_token: refreshToken };
  }

  async performPasswordReset(token: string, newPassword: string) {
    const unexpiredResetTokens = await this.prisma.passwordResetToken.findMany({
      where: {
        expiresAt: {
          gte: new Date(),
        },
      },
      select: {
        id: true,
        hashedResetToken: true,
        userId: true,
        expiresAt: true,
      },
    });

    if (!unexpiredResetTokens.length) {
      throw new UnauthorizedException('Invalid or expired reset token.');
    }

    let validTokenRecord: Token | null = null;
    for (const record of unexpiredResetTokens) {
      const isMatch = await bcrypt.compare(token, record.hashedResetToken);
      if (isMatch) {
        validTokenRecord = record;
        break;
      }
    }

    if (!validTokenRecord) {
      throw new UnauthorizedException('Invalid or expired reset token.');
    }
    const salt = await bcrypt.genSalt(10);
    const newHashedPassword = await bcrypt.hash(newPassword, salt);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const updatedPassword = await this.prisma.user.update({
      where: { id: validTokenRecord.userId },
      data: {
        password: newHashedPassword,
      },
    });

    await this.prisma.passwordResetToken.delete({
      where: { id: validTokenRecord.id },
    });

    return { message: 'Password reset successful. You may now log in.' };
  }

  async switchOrganization(userId: string, orgId: string) {
    const membership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: { userId, organizationId: orgId },
      },
      include: { user: true, role: true },
    });

    if (!membership) {
      throw new NotFoundException(
        'Membership in the target organization not found.',
      );
    }

    await this.auditService.log({
      action: 'USER_SWITCH_ORGANIZATION',
      actingUserId: userId,
      organizationId: orgId,
    });

    // We can now reuse our main token generation function, passing the user and new membership.
    return this.getTokensForUser(membership.user, membership);
  }
}
