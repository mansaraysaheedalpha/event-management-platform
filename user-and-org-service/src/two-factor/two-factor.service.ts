// src/two-factor/two-factor.service.ts
import { Injectable, UnauthorizedException, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as speakeasy from 'speakeasy';
import * as qrcode from 'qrcode';
import { PrismaService } from 'src/prisma.service';
import { encrypt, decrypt } from 'src/common/utils/encryption.util';
import { AuditService } from 'src/audit/audit.service';

@Injectable()
export class TwoFactorService {
  private readonly logger = new Logger(TwoFactorService.name);
  private readonly encryptionKey: string;

  constructor(
    private prisma: PrismaService,
    private configService: ConfigService,
    private auditService: AuditService,
  ) {
    this.encryptionKey = this.configService.get<string>('ENCRYPTION_KEY');
    if (!this.encryptionKey) {
      throw new Error('ENCRYPTION_KEY is not configured');
    }
  }

  async setup2FA(userId: string) {
    // Fetch user to get their email
  const user = await this.prisma.user.findUniqueOrThrow({
    where: { id: userId },
    select: { email: true },
  });

    const secret = speakeasy.generateSecret({
      name: user.email,
      issuer: 'GlobalConnect',
    });

    const otpAuthUrl = secret.otpauth_url;

    if (!otpAuthUrl) {
      throw new Error('Failed to generate OTP Auth URL');
    }

    const qrCodeDataUrl = await qrcode.toDataURL(otpAuthUrl);

    // Encrypt the secret before storing
    const encryptedSecret = encrypt(secret.base32, this.encryptionKey);

    await this.prisma.user.update({
      where: { id: userId },
      data: {
        twoFactorSecret: encryptedSecret,
        isTwoFactorEnabled: false,
      },
    });

    this.logger.log(`2FA setup initiated for user ${userId}`);

    return { qrCodeDataUrl };
  }

  async is2FACodeValid(userId: string, code: string): Promise<boolean> {
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });

    if (!user.twoFactorSecret) {
      return false;
    }

    // Decrypt the secret before validating
    let decryptedSecret: string;
    try {
      decryptedSecret = decrypt(user.twoFactorSecret, this.encryptionKey);
    } catch (error) {
      this.logger.error(`Failed to decrypt 2FA secret for user ${userId}`, error);
      return false;
    }

    return speakeasy.totp.verify({
      secret: decryptedSecret,
      encoding: 'base32',
      token: code,
    });
  }

  async turnOn2FA(userId: string, code: string) {
    const isCodeValid = await this.is2FACodeValid(userId, code);

    if (!isCodeValid) {
      throw new UnauthorizedException('Invalid 2FA code.');
    }

    await this.prisma.user.update({
      where: { id: userId },
      data: { isTwoFactorEnabled: true },
    });

    await this.auditService.log({
      action: 'TWO_FACTOR_ENABLED',
      actingUserId: userId,
    });

    this.logger.log(`2FA enabled for user ${userId}`);

    return {
      message: 'Two-Factor Authentication has been enabled successfully.',
    };
  }

  async turnOff2FA(userId: string) {
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        isTwoFactorEnabled: false,
        twoFactorSecret: null,
      },
    });

    await this.auditService.log({
      action: 'TWO_FACTOR_DISABLED',
      actingUserId: userId,
    });

    this.logger.log(`2FA disabled for user ${userId}`);

    return { message: 'Two-Factor Authentication has been disabled.' };
  }
}
