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
import { User, Membership, Role as PrismaRole } from '@prisma/client';
import { JwtPayload } from 'src/common/interfaces/auth.interface';

// FIX: The missing 'Token' interface for password reset
interface Token {
  id: string;
  hashedResetToken: string;
  userId: string;
  expiresAt: Date;
}

// This is now the SINGLE SOURCE OF TRUTH for the user data needed to generate tokens.
type UserForToken = Pick<
  User,
  | 'id'
  | 'email'
  | 'first_name'
  | 'last_name'
  | 'imageUrl'
  | 'tier'
  | 'preferredLanguage'
  | 'sponsorId'
  | 'isTwoFactorEnabled'
>;

type MembershipForToken = Membership & { role: PrismaRole };

type UserForLogin = UserForToken & {
  password?: string;
  memberships: MembershipForToken[];
};

type OnboardingResponse = {
  onboardingToken: string;
  user: UserForLogin;
};

type LoginResponse =
  | { requires2FA: true; userId: string }
  | { access_token: string; refresh_token: string }
  | OnboardingResponse;

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly mailerService: MailerService,
    private twoFactorService: TwoFactorService,
    private auditService: AuditService,
  ) {}

  private async getOnboardingToken(userId: string): Promise<string> {
    const payload = { sub: userId, scope: 'onboarding' };
    return this.jwtService.signAsync(payload, {
      secret: this.configService.get<string>('JWT_SECRET'),
      expiresIn: '15m',
    });
  }

  async login(loginDTO: LoginDTO): Promise<LoginResponse> {
    // NOTE: This 'select' clause now fetches all fields required by UserForToken
    const existingUser = await this.prisma.user.findUnique({
      where: { email: loginDTO.email },
      select: {
        id: true,
        email: true,
        password: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        isTwoFactorEnabled: true,
        preferredLanguage: true,
        tier: true,
        sponsorId: true,
        memberships: { include: { role: true } },
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

    if (existingUser.memberships.length === 0) {
      const onboardingToken = await this.getOnboardingToken(existingUser.id);
      return {
        onboardingToken,
        user: existingUser,
      };
    }

    if (existingUser.isTwoFactorEnabled) {
      return { requires2FA: true, userId: existingUser.id };
    }

    const defaultMembership = existingUser.memberships[0];
    await this.auditService.log({
      action: 'USER_LOGIN',
      actingUserId: existingUser.id,
      organizationId: defaultMembership.organizationId,
    });
    return this.getTokensForUser(existingUser, defaultMembership);
  }

  async login2FA(userId: string, twoFactorCode: string) {
    // NOTE: This 'select' clause is now IDENTICAL to the one in login()
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        isTwoFactorEnabled: true,
        preferredLanguage: true,
        tier: true,
        sponsorId: true,
        memberships: { include: { role: true } },
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
    await this.prisma.user.updateMany({
      where: { id: userId, hashedRefreshToken: { not: null } },
      data: { hashedRefreshToken: null },
    });
    await this.auditService.log({
      action: 'USER_LOGOUT',
      actingUserId: userId,
    });
  }

  async refreshTokenService(userId: string, incomingRefreshToken: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      // NOTE: This 'select' clause is now IDENTICAL to the one in login()
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        isTwoFactorEnabled: true,
        preferredLanguage: true,
        tier: true,
        sponsorId: true,
        hashedRefreshToken: true, // Also include the refresh token
        memberships: { include: { role: true } },
      },
    });

    if (!user || !user.hashedRefreshToken || !user.memberships.length) {
      throw new ForbiddenException('Access Denied');
    }

    const payload = this.jwtService.decode(incomingRefreshToken);
    const refreshTokenId = payload.jti;
    const isRefreshTokenMatch = await bcrypt.compare(
      refreshTokenId,
      user.hashedRefreshToken,
    );

    if (!isRefreshTokenMatch) {
      throw new ForbiddenException('Access Denied: Refresh token mismatch.');
    }

    const relevantMembership =
      user.memberships.find((m) => m.organizationId === payload.orgId) ||
      user.memberships[0];

    return this.getTokensForUser(user, relevantMembership);
  }

  async getTokensForUser(user: UserForToken, membership: MembershipForToken) {
    const organization = await this.prisma.organization.findUnique({
      where: { id: membership.organizationId },
    });
    if (!organization) {
      throw new NotFoundException(
        'Organization data could not be found for membership.',
      );
    }

    const refreshTokenId = randomBytes(32).toString('hex');
    const accessTokenPayload: JwtPayload = {
      sub: user.id,
      email: user.email,
      orgId: membership.organizationId,
      role: membership.role.name,
      permissions: [], // Permissions logic can be added later
      tier: (user.tier as 'default' | 'vip') || 'default',
      preferredLanguage: user.preferredLanguage || 'en',
      sponsorId: user.sponsorId || undefined,
      orgRequires2FA: organization.isTwoFactorRequired ?? false,
      is2FAEnabled: user.isTwoFactorEnabled,
    };
    const refreshTokenPayload = {
      sub: user.id,
      jti: refreshTokenId,
      orgId: membership.organizationId,
    };

    const [accessToken, refreshToken] = await Promise.all([
      this.jwtService.signAsync(accessTokenPayload, {
        secret: this.configService.get<string>('JWT_SECRET'),
        expiresIn: '15m', // Changed to 15m for easier testing
      }),
      this.jwtService.signAsync(refreshTokenPayload, {
        secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
        expiresIn: '7d',
      }),
    ]);

    const hashedRefreshToken = await bcrypt.hash(refreshTokenId, 10);
    await this.prisma.user.update({
      where: { id: user.id },
      data: { hashedRefreshToken },
    });

    return { access_token: accessToken, refresh_token: refreshToken };
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
