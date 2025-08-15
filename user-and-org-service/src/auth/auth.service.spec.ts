import { Test, TestingModule } from '@nestjs/testing';
import { AuthService } from './auth.service';
import { PrismaService } from 'src/prisma.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { MailerService } from '@nestjs-modules/mailer';
import { TwoFactorService } from 'src/two-factor/two-factor.service';
import { AuditService } from 'src/audit/audit.service';
import { PermissionsService } from 'src/permissions/permissions.service';
import {
  
  NotFoundException,
} from '@nestjs/common';
import * as bcrypt from 'bcrypt';

jest.mock('bcrypt');

describe('AuthService', () => {
  let module: TestingModule;
  let service: AuthService;
  let prisma: PrismaService;
  let jwtService: JwtService;
  let mailerService: MailerService;

  const mockUser = {
    id: 'user-1',
    email: 'test@example.com',
    password: 'hashedpassword',
    hashedRefreshToken: 'hashed-refresh-token-id',
    isTwoFactorEnabled: false,
    memberships: [
      {
        organizationId: 'org-1',
        role: { id: 'role-1', name: 'ADMIN' },
      },
    ],
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        AuthService,
        {
          provide: PrismaService,
          useValue: {
            user: {
              findUnique: jest.fn(),
              update: jest.fn(),
              findUniqueOrThrow: jest.fn(),
            },
            passwordResetToken: {
              deleteMany: jest.fn(),
              create: jest.fn(),
              findMany: jest.fn(),
              delete: jest.fn(),
            },
            role: { findUnique: jest.fn() },
            membership: { findUnique: jest.fn() },
          },
        },
        {
          provide: JwtService,
          useValue: { signAsync: jest.fn(), decode: jest.fn() },
        },
        { provide: ConfigService, useValue: { get: jest.fn() } },
        { provide: MailerService, useValue: { sendMail: jest.fn() } },
        { provide: TwoFactorService, useValue: { is2FACodeValid: jest.fn() } },
        { provide: AuditService, useValue: { log: jest.fn() } },
        { provide: PermissionsService, useValue: {} },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    prisma = module.get<PrismaService>(PrismaService);
    jwtService = module.get<JwtService>(JwtService);
    mailerService = module.get<MailerService>(MailerService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('login', () => {
    it('should return tokens for a valid user without 2FA', async () => {
      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser as any);
      (bcrypt.compare as jest.Mock).mockResolvedValue(true);
      jest.spyOn(jwtService, 'signAsync').mockResolvedValue('mock-token');

      // **THE FIX**: Provide a mock object that matches the shape Prisma expects.
      const mockRoleWithPermissions = {
        id: 'role-1',
        name: 'ADMIN',
        permissions: [{ name: 'users:create' }], // An array of objects with a 'name' property
      };
      jest
        .spyOn(prisma.role, 'findUnique')
        .mockResolvedValue(mockRoleWithPermissions as any);

      const result = await service.login({
        email: 'test@example.com',
        password: 'password',
      });
      expect(result).toHaveProperty('access_token');
    });
  });

  describe('switchOrganization', () => {
    it('should issue new tokens for a valid organization switch', async () => {
      const newMembership = {
        organizationId: 'org-2',
        role: { id: 'role-2', name: 'MEMBER' },
        user: mockUser,
      };
      jest
        .spyOn(prisma.membership, 'findUnique')
        .mockResolvedValue(newMembership as any);
      jest.spyOn(jwtService, 'signAsync').mockResolvedValue('new-org-token');

      // **THE FIX**: Also provide the correct mock shape here.
      const mockRoleWithPermissions = {
        id: 'role-2',
        name: 'MEMBER',
        permissions: [], // Can be empty, but must be an array of objects
      };
      jest
        .spyOn(prisma.role, 'findUnique')
        .mockResolvedValue(mockRoleWithPermissions as any);

      const result = await service.switchOrganization(mockUser.id, 'org-2');
      expect(result).toHaveProperty('access_token');
    });

    it('should throw NotFoundException if user is not a member of the target org', async () => {
      jest.spyOn(prisma.membership, 'findUnique').mockResolvedValue(null);
      await expect(
        service.switchOrganization(mockUser.id, 'org-non-member'),
      ).rejects.toThrow(NotFoundException);
    });
  });
});
