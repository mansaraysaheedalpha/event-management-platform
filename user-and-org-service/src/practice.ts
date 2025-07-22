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
import { User } from '@prisma/client';



// ... interface Token and type LoginResponse remain the same

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly mailerService: MailerService,
    private readonly twoFactorService: TwoFactorService,
    private readonly auditService: AuditService,
  ) {}

  async login(loginDTO: LoginDTO): Promise<LoginResponse> {
    const existingUser = await this.prisma.user.findUnique({
      where: { email: loginDTO.email },
      include: {
        // We need to know the user's memberships to log them into an organization
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
      return { requires2FA: true, userId: existingUser.id };
    }

    // --- REFINEMENT: Find a default organization to log into ---
    // If the user is part of any organization, we log them into the first one.
    // A more advanced implementation could use a `lastUsedOrgId` field on the User model.
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
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
      include: { memberships: true },
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
    // Your Question: "I am not sure if this check is valid for a logged in user to not exists in the data"
    // Your instinct is correct. This check is redundant. The AuthGuard('jwt') already validated
    // the token and confirmed the user exists. We can safely perform the update directly.
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
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      include: { memberships: { where: { userId } } }, // Also fetch memberships
    });

    if (!user || !user.hashedRefreshToken || !user.memberships.length) {
      throw new ForbiddenException('Access Denied');
    }

    const payload = this.jwtService.decode(incomingRefreshToken) as {
      jti: string;
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

    // Find the membership associated with the orgId from the old token
    const oldTokenPayload = this.jwtService.decode(incomingRefreshToken) as {
      orgId: string;
    };
    const relevantMembership =
      user.memberships.find(
        (m) => m.organizationId === oldTokenPayload.orgId,
      ) || user.memberships[0];

    return this.getTokensForUser(user, relevantMembership);
  }

  // --- REFACTORED getTokensForUser ---
  // It now requires a membership object to know the user's role and organization.
  async getTokensForUser(
    user: { id: string; email: string },
    membership: { organizationId: string; role: string },
  ) {
    const refreshTokenId = randomBytes(32).toString('hex');
    const userRole = membership.role as Role;

    // Look up permissions based on the role. Default to empty array if role is unknown.
    const permissions = rolePermissions[userRole] || [];

    const accessTokenPayload = {
      sub: user.id,
      email: user.email,
      orgId: membership.organizationId,
      role: userRole,
      permissions: permissions, // <-- THE MAGIC: Permissions are now in the token!
    };

    const refreshTokenPayload = {
      sub: user.id,
      jti: refreshTokenId,
      orgId: membership.organizationId, // Include orgId to maintain context on refresh
    };

    const accessToken = this.jwtService.sign(accessTokenPayload, {
      secret: this.configService.get<string>('JWT_SECRET'),
      expiresIn: '15m',
    });

    const refreshToken = this.jwtService.sign(refreshTokenPayload, {
      secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
      expiresIn: '7d',
    });

    const hashedRefreshToken = await bcrypt.hash(refreshTokenId, 10);
    await this.prisma.user.update({
      where: { id: user.id },
      data: { hashedRefreshToken: hashedRefreshToken },
    });

    return { access_token: accessToken, refresh_token: refreshToken };
  }

  // --- REFACTORED switchOrganization ---
  async switchOrganization(userId: string, orgId: string) {
    const membership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: { userId, organizationId: orgId },
      },
      include: { user: true },
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

  // ... handlePasswordResetRequest and performPasswordReset remain the same ...
  async handlePasswordResetRequest(email: string) {
    // ...
  }
  async performPasswordReset(token: string, newPassword: string) {
    // ...
  }
}
