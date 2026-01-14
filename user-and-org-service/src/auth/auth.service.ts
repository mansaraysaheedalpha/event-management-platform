// src/auth/auth.service.ts
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
import { EmailService } from 'src/email/email.service';
import { TwoFactorService } from 'src/two-factor/two-factor.service';
import { AuditService } from 'src/audit/audit.service';
import {
  User,
  Membership,
  Role as PrismaRole,
  Permission,
} from '@prisma/client';
import { JwtPayload } from 'src/common/interfaces/auth.interface';

interface Token {
  id: string;
  hashedResetToken: string;
  userId: string;
  expiresAt: Date;
}

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
  | 'userType'
>;

type RoleWithPermissions = PrismaRole & { permissions: Permission[] };
type MembershipForToken = Membership & { role: RoleWithPermissions };

type UserForLogin = UserForToken & {
  password?: string;
  memberships: MembershipForToken[];
};

type OnboardingResponse = {
  onboardingToken: string;
  user: UserForLogin;
};

// Response type for attendee login (token without orgId)
type AttendeeTokenResponse = {
  access_token: string;
  refresh_token: string;
  isAttendee: true;
};

type LoginResponse =
  | { requires2FA: true; userId: string }
  | { access_token: string; refresh_token: string }
  | OnboardingResponse
  | AttendeeTokenResponse;

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly emailService: EmailService,
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

  private readonly MAX_LOGIN_ATTEMPTS = 5;
  private readonly LOCKOUT_DURATION_MINUTES = 15;

  async login(loginDTO: LoginDTO): Promise<LoginResponse> {
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
        userType: true,
        failedLoginAttempts: true,
        lockedUntil: true,
        memberships: {
          include: {
            role: {
              include: {
                permissions: true,
              },
            },
          },
        },
      },
    });

    if (!existingUser) {
      throw new UnauthorizedException('Invalid credentials');
    }

    // Check if account is locked
    if (existingUser.lockedUntil && existingUser.lockedUntil > new Date()) {
      // Don't reveal that account is locked - use generic message
      throw new UnauthorizedException('Invalid credentials');
    }

    const isMatch = await bcrypt.compare(
      loginDTO.password,
      existingUser.password,
    );
    if (!isMatch) {
      // Increment failed login attempts
      const newFailedAttempts = existingUser.failedLoginAttempts + 1;
      const updateData: { failedLoginAttempts: number; lockedUntil?: Date } = {
        failedLoginAttempts: newFailedAttempts,
      };

      // Lock account if max attempts reached
      if (newFailedAttempts >= this.MAX_LOGIN_ATTEMPTS) {
        const lockUntil = new Date();
        lockUntil.setMinutes(lockUntil.getMinutes() + this.LOCKOUT_DURATION_MINUTES);
        updateData.lockedUntil = lockUntil;

        await this.auditService.log({
          action: 'ACCOUNT_LOCKED',
          actingUserId: existingUser.id,
          details: { reason: 'Too many failed login attempts', lockedUntil: lockUntil },
        });
      }

      await this.prisma.user.update({
        where: { id: existingUser.id },
        data: updateData,
      });

      throw new UnauthorizedException('Invalid credentials');
    }

    // Reset failed login attempts on successful login
    if (existingUser.failedLoginAttempts > 0 || existingUser.lockedUntil) {
      await this.prisma.user.update({
        where: { id: existingUser.id },
        data: {
          failedLoginAttempts: 0,
          lockedUntil: null,
        },
      });
    }

    // Handle 2FA first (applies to both organizers and attendees)
    if (existingUser.isTwoFactorEnabled) {
      return { requires2FA: true, userId: existingUser.id };
    }

    // Check if user is an ATTENDEE - they never need organizations
    if (existingUser.userType === 'ATTENDEE') {
      await this.auditService.log({
        action: 'USER_LOGIN',
        actingUserId: existingUser.id,
      });
      return this.getTokensForAttendee(existingUser);
    }

    // User is an ORGANIZER - check if they have an organization
    if (existingUser.memberships.length === 0) {
      // Organizer without organization - needs onboarding
      const onboardingToken = await this.getOnboardingToken(existingUser.id);
      return {
        onboardingToken,
        user: existingUser,
      };
    }

    // Organizer with organization - return normal token with orgId
    const defaultMembership = existingUser.memberships[0];
    await this.auditService.log({
      action: 'USER_LOGIN',
      actingUserId: existingUser.id,
      organizationId: defaultMembership.organizationId,
    });
    return this.getTokensForUser(existingUser, defaultMembership);
  }

  async login2FA(userId: string, twoFactorCode: string) {
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
        userType: true,
        memberships: {
          include: {
            role: {
              include: {
                permissions: true,
              },
            },
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
        userType: true,
        hashedRefreshToken: true,
        memberships: {
          include: {
            role: {
              include: {
                permissions: true,
              },
            },
          },
        },
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
    const existingPermissions = membership.role.permissions.map((p) => p.name);

    // Base permissions that all org members get
    const additionalPermissions = ['content:manage'];

    // Backchannel access for OWNER, ADMIN, MODERATOR, and SPEAKER roles
    if (['OWNER', 'ADMIN', 'MODERATOR', 'SPEAKER'].includes(membership.role.name)) {
      additionalPermissions.push('backchannel:join', 'backchannel:send');
    }

    // Presentation control for SPEAKER role
    if (membership.role.name === 'SPEAKER') {
      additionalPermissions.push('presentation:control');
    }

    const accessTokenPayload: JwtPayload = {
      sub: user.id,
      email: user.email,
      orgId: membership.organizationId,
      role: membership.role.name,
      permissions: [...new Set([...existingPermissions, ...additionalPermissions])],
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
        expiresIn: '30m',
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

  /**
   * Generate tokens for attendee users (no organization required).
   * JWT payload does NOT include orgId.
   */
  async getTokensForAttendee(
    user: UserForToken,
  ): Promise<AttendeeTokenResponse> {
    const refreshTokenId = randomBytes(32).toString('hex');

    // Attendee JWT payload - no orgId, no role, minimal permissions
    const accessTokenPayload: Omit<JwtPayload, 'orgId' | 'role' | 'orgRequires2FA'> = {
      sub: user.id,
      email: user.email,
      permissions: [], // Attendees have no special permissions
      tier: (user.tier as 'default' | 'vip') || 'default',
      preferredLanguage: user.preferredLanguage || 'en',
      sponsorId: user.sponsorId || undefined,
      is2FAEnabled: user.isTwoFactorEnabled,
    };

    const refreshTokenPayload = {
      sub: user.id,
      jti: refreshTokenId,
      // Note: no orgId for attendees
    };

    const [accessToken, refreshToken] = await Promise.all([
      this.jwtService.signAsync(accessTokenPayload, {
        secret: this.configService.get<string>('JWT_SECRET'),
        expiresIn: '30m',
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

    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      isAttendee: true,
    };
  }

  async handlePasswordResetRequest(email: string) {
    const user = await this.prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
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

    const resetUrl = `${this.configService.get('FRONTEND_URL')}/reset-password?token=${rawResetToken}`;

    await this.emailService.sendPasswordResetEmail(
      user.email,
      user.first_name || 'there',
      resetUrl,
    );

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

    // Timing-safe: always iterate through ALL tokens without early exit
    let validTokenRecord: Token | null = null;
    for (const record of unexpiredResetTokens) {
      const isMatch = await bcrypt.compare(token, record.hashedResetToken);
      if (isMatch && !validTokenRecord) {
        validTokenRecord = record;
        // Continue iterating to prevent timing attacks
      }
    }

    if (!validTokenRecord) {
      throw new UnauthorizedException('Invalid or expired reset token.');
    }
    const salt = await bcrypt.genSalt(10);
    const newHashedPassword = await bcrypt.hash(newPassword, salt);
    await this.prisma.user.update({
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
      include: {
        user: true,
        role: {
          include: {
            permissions: true,
          },
        },
      },
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

    return this.getTokensForUser(membership.user, membership);
  }

  /**
   * Register a new attendee user.
   * Attendees are created with userType='ATTENDEE' and don't need organizations.
   * Returns tokens immediately (no onboarding required).
   */
  async registerAttendee(input: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) {
    // Check if email already exists
    const existingUser = await this.prisma.user.findUnique({
      where: { email: input.email },
    });

    if (existingUser) {
      throw new ForbiddenException('An account with this email already exists.');
    }

    // Hash the password
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(input.password, salt);

    // Create the attendee user with userType='ATTENDEE'
    const newUser = await this.prisma.user.create({
      data: {
        email: input.email,
        password: hashedPassword,
        first_name: input.first_name,
        last_name: input.last_name,
        userType: 'ATTENDEE', // Mark as attendee
      },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        tier: true,
        preferredLanguage: true,
        sponsorId: true,
        isTwoFactorEnabled: true,
        userType: true,
      },
    });

    await this.auditService.log({
      action: 'USER_REGISTER_ATTENDEE',
      actingUserId: newUser.id,
    });

    // Generate tokens for the new attendee (no orgId)
    const tokens = await this.getTokensForAttendee(newUser);

    return {
      user: newUser,
      tokens,
    };
  }
}
