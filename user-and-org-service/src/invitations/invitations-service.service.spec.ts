import { Test, TestingModule } from '@nestjs/testing';
import { InvitationsService } from './invitations.service';
import { PrismaService } from '../prisma.service';
import { MailerService } from '@nestjs-modules/mailer';
import { UnauthorizedException } from '@nestjs/common';

// Mock the Prisma client
const db = {
  role: {
    findUnique: jest.fn(),
  },
  invitation: {
    create: jest.fn(),
    findMany: jest.fn(),
    delete: jest.fn(),
  },
  user: {
    findUnique: jest.fn(),
    create: jest.fn(),
  },
  membership: {
    create: jest.fn(),
  },
  $transaction: jest.fn().mockImplementation((callback) => callback(db)),
};

describe('InvitationsService', () => {
  let service: InvitationsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        InvitationsService,
        { provide: PrismaService, useValue: db },
        { provide: MailerService, useValue: { sendMail: jest.fn() } },
      ],
    }).compile();

    service = module.get<InvitationsService>(InvitationsService);
    // Clear all mock history before each test
    jest.clearAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('create', () => {
    it('should create an invitation and send an email', async () => {
      // ARRANGE
      const roleData = { id: 'role_123', name: 'MEMBER' };
      db.role.findUnique.mockResolvedValue(roleData);
      db.invitation.create.mockResolvedValue({
        email: 'new-user@example.com',
        organization: { name: 'Test Org' },
        invitedBy: { first_name: 'Saheed', last_name: 'Alpha' },
      });

      // ACT
      const result = await service.create({
        email: 'new-user@example.com',
        role: 'MEMBER',
        organizationId: 'org_123',
        invitedById: 'user_123',
      });

      // ASSERT
      expect(db.role.findUnique).toHaveBeenCalled();
      expect(db.invitation.create).toHaveBeenCalled();
      expect(result.message).toContain('Invitation successfully sent');
    });
  });

  describe('accept', () => {
    it('should create a new user and membership when a valid token is accepted', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'invited@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        role: { id: 'role_123', name: 'MEMBER' },
        expiresAt: new Date(Date.now() + 1000 * 60 * 60), // Expires in 1 hour
      };
      const acceptDto = {
        first_name: 'Invited',
        last_name: 'User',
        password: 'password123',
      };

      // Mock the bcrypt.compare function, which we can't easily access
      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(null); // Simulate user does not exist
      db.user.create.mockResolvedValue({ id: 'new_user_123', ...acceptDto });
      db.membership.create.mockResolvedValue({
        userId: 'new_user_123',
        organizationId: 'org_123',
      });

      // ACT
      const result = await service.accept('valid_raw_token', acceptDto);

      // ASSERT
      expect(result).toBeDefined();
      expect(result.user).toHaveProperty('id');
      expect(result.membership).toBeDefined();
      expect(db.user.create).toHaveBeenCalled();
      expect(db.membership.create).toHaveBeenCalled();
      expect(db.invitation.delete).toHaveBeenCalledWith({
        where: { id: mockInvitation.id },
      });
    });

    it('should throw an error for an invalid token', async () => {
      // ARRANGE
      db.invitation.findMany.mockResolvedValue([]); // No invitations found

      // ACT & ASSERT
      await expect(service.accept('invalid_token', {} as any)).rejects.toThrow(
        UnauthorizedException,
      );
    });
  });
});
