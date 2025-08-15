import { Test, TestingModule } from '@nestjs/testing';
import { TwoFactorService } from './two-factor.service';
import { PrismaService } from 'src/prisma.service';
import { UnauthorizedException } from '@nestjs/common';
import * as speakeasy from 'speakeasy';
import * as qrcode from 'qrcode';

// Mock the external libraries
jest.mock('speakeasy');
jest.mock('qrcode');

describe('TwoFactorService', () => {
  let service: TwoFactorService;
  let prisma: PrismaService;
  let module: TestingModule;

  const mockUser = {
    id: 'user-1',
    twoFactorSecret: 'MOCK_SECRET',
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        TwoFactorService,
        {
          provide: PrismaService,
          useValue: {
            user: { update: jest.fn(), findUniqueOrThrow: jest.fn() },
          },
        },
      ],
    }).compile();

    service = module.get<TwoFactorService>(TwoFactorService);
    prisma = module.get<PrismaService>(PrismaService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('setup2FA', () => {
    it('should generate a secret, a QR code, and update the user', async () => {
      const mockSecret = {
        base32: 'MOCK_SECRET_BASE32',
        otpauth_url: 'otpauth://...',
      };
      (speakeasy.generateSecret as jest.Mock).mockReturnValue(mockSecret);
      (qrcode.toDataURL as jest.Mock).mockResolvedValue(
        'data:image/png;base64,...',
      );

      const result = await service.setup2FA(mockUser.id);

      expect(speakeasy.generateSecret).toHaveBeenCalled();
      expect(qrcode.toDataURL).toHaveBeenCalledWith(mockSecret.otpauth_url);
      expect(prisma.user.update).toHaveBeenCalledWith({
        where: { id: mockUser.id },
        data: {
          twoFactorSecret: mockSecret.base32,
          isTwoFactorEnabled: false,
        },
      });
      expect(result).toHaveProperty('qrCodeDataUrl');
    });
  });

  describe('is2FACodeValid', () => {
    it('should return true for a valid code', async () => {
      jest
        .spyOn(prisma.user, 'findUniqueOrThrow')
        .mockResolvedValue(mockUser as any);
      (speakeasy.totp.verify as jest.Mock).mockReturnValue(true);

      const isValid = await service.is2FACodeValid(mockUser.id, 'valid_code');

      expect(isValid).toBe(true);
      expect(speakeasy.totp.verify).toHaveBeenCalledWith({
        secret: mockUser.twoFactorSecret,
        encoding: 'base32',
        token: 'valid_code',
      });
    });
  });

  describe('turnOn2FA', () => {
    it('should enable 2FA for a user with a valid code', async () => {
      // Mock the internal call to is2FACodeValid to return true
      jest.spyOn(service, 'is2FACodeValid').mockResolvedValue(true);

      const result = await service.turnOn2FA(mockUser.id, 'valid_code');

      expect(prisma.user.update).toHaveBeenCalledWith({
        where: { id: mockUser.id },
        data: { isTwoFactorEnabled: true },
      });
      expect(result.message).toContain('enabled successfully');
    });

    it('should throw UnauthorizedException for an invalid code', async () => {
      jest.spyOn(service, 'is2FACodeValid').mockResolvedValue(false);

      await expect(
        service.turnOn2FA(mockUser.id, 'invalid_code'),
      ).rejects.toThrow(UnauthorizedException);
    });
  });
});
