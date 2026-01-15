// src/two-factor/two-factor.service.ts
import {
  Injectable,
  UnauthorizedException,
  BadRequestException,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as speakeasy from 'speakeasy';
import * as qrcode from 'qrcode';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';
import { PrismaService } from 'src/prisma.service';
import { encrypt, decrypt } from 'src/common/utils/encryption.util';
import { AuditService } from 'src/audit/audit.service';
import { EmailService } from 'src/email/email.service';

// Email backup code expires after 10 minutes
const EMAIL_BACKUP_CODE_EXPIRY_MINUTES = 10;

@Injectable()
export class TwoFactorService {
  private readonly logger = new Logger(TwoFactorService.name);
  private readonly encryptionKey: string;

  constructor(
    private prisma: PrismaService,
    private configService: ConfigService,
    private auditService: AuditService,
    private emailService: EmailService,
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

  /**
   * Generate and send a 6-digit backup code to user's email.
   * Used when user cannot access their authenticator app.
   */
  async sendEmailBackupCode(userId: string): Promise<{ message: string }> {
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        first_name: true,
        isTwoFactorEnabled: true,
      },
    });

    // Only allow for users with 2FA enabled
    if (!user.isTwoFactorEnabled) {
      throw new BadRequestException(
        'Two-Factor Authentication is not enabled for this account.',
      );
    }

    // Generate a cryptographically secure 6-digit code
    const code = crypto.randomInt(100000, 999999).toString();

    // Hash the code before storing
    const hashedCode = await bcrypt.hash(code, 10);

    // Set expiration time
    const expiresAt = new Date(
      Date.now() + EMAIL_BACKUP_CODE_EXPIRY_MINUTES * 60 * 1000,
    );

    // Store the hashed code and expiration
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        emailBackupCode: hashedCode,
        emailBackupCodeExpiresAt: expiresAt,
      },
    });

    // Send the code via email
    await this.emailService.sendBackupCodeEmail(
      user.email,
      user.first_name,
      code,
      EMAIL_BACKUP_CODE_EXPIRY_MINUTES,
    );

    await this.auditService.log({
      action: 'EMAIL_BACKUP_CODE_SENT',
      actingUserId: userId,
    });

    this.logger.log(`Email backup code sent to user ${userId}`);

    // Mask email for response (show only first 2 and last 2 chars before @)
    const [localPart, domain] = user.email.split('@');
    const maskedEmail =
      localPart.length > 4
        ? `${localPart.slice(0, 2)}***${localPart.slice(-2)}@${domain}`
        : `${localPart[0]}***@${domain}`;

    return {
      message: `A verification code has been sent to ${maskedEmail}. It expires in ${EMAIL_BACKUP_CODE_EXPIRY_MINUTES} minutes.`,
    };
  }

  /**
   * Verify the email backup code.
   * Returns true if valid, throws exception if invalid/expired.
   */
  async verifyEmailBackupCode(userId: string, code: string): Promise<boolean> {
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: {
        emailBackupCode: true,
        emailBackupCodeExpiresAt: true,
      },
    });

    // Check if code exists
    if (!user.emailBackupCode || !user.emailBackupCodeExpiresAt) {
      throw new UnauthorizedException(
        'No backup code has been requested. Please request a new code.',
      );
    }

    // Check if code has expired
    if (new Date() > user.emailBackupCodeExpiresAt) {
      // Clear expired code
      await this.prisma.user.update({
        where: { id: userId },
        data: {
          emailBackupCode: null,
          emailBackupCodeExpiresAt: null,
        },
      });
      throw new UnauthorizedException(
        'Backup code has expired. Please request a new code.',
      );
    }

    // Verify the code
    const isValid = await bcrypt.compare(code, user.emailBackupCode);

    if (!isValid) {
      throw new UnauthorizedException('Invalid backup code.');
    }

    // Clear the code after successful verification (single use)
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        emailBackupCode: null,
        emailBackupCodeExpiresAt: null,
      },
    });

    await this.auditService.log({
      action: 'EMAIL_BACKUP_CODE_VERIFIED',
      actingUserId: userId,
    });

    this.logger.log(`Email backup code verified for user ${userId}`);

    return true;
  }
}
