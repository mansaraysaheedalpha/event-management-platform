//src/two-factor/two-factor.service.s
import { Injectable, UnauthorizedException } from '@nestjs/common';
import * as speakeasy from 'speakeasy';
import * as qrcode from 'qrcode';
import { PrismaService } from 'src/prisma.service';

@Injectable()
export class TwoFactorService {
  constructor(private prisma: PrismaService) {}
  async setup2FA(userId: string) {
    const secret = speakeasy.generateSecret({
      name: 'GlobalConnect (myemaildomain.com)',
      issuer: 'GlobalConnect',
    });

    const otpAuthUrl = secret.otpauth_url;

    if (!otpAuthUrl) {
      throw new Error('Failed to generate OTP Auth URL');
    }

    const qrCodeDataUrl = await qrcode.toDataURL(otpAuthUrl);

    await this.prisma.user.update({
      where: { id: userId },
      data: {
        twoFactorSecret: secret.base32,
        isTwoFactorEnabled: false,
      },
    });

    return { qrCodeDataUrl };
  }

  async is2FACodeValid(userId: string, code: string): Promise<boolean> {
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });

    if (!user.twoFactorSecret) {
      return false;
    }

    return speakeasy.totp.verify({
      secret: user.twoFactorSecret,
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

    return {
      message: 'Two-Factor Authentication has been enabled successfully.',
    };
  }
}
